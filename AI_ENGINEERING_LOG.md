# AI Engineering Log

This project was built across three sessions using **Claude Code** (Anthropic's agentic CLI, running
Claude Sonnet 5) as the sole development tool — planning, code generation, test writing, and
debugging. The product itself additionally integrates an LLM API and, as of session 2, the
**Gemini embeddings API** as runtime features (NL→rule authoring, cold-start recommendations,
ruleset review, purchase-history similarity, RAG-based conflict-checking as of session 3) — those
are features of the shipped app, not a build-tool; documented separately in the README under
"AI features." **Note:** sessions 1-2 below describe the LLM provider as "Grok (xAI)", which was the
original intent — session 3 discovered the configured API key was actually for Groq (a different,
unrelated provider with a confusingly similar name) and corrected the provider references
throughout; see §7. The sessions 1-2 text is left as originally written rather than silently
rewritten, since it accurately reflects what was built and believed at the time.

## 1. AI tools used

- **Claude Code (Sonnet 5)** — used for the entire SDLC across both sessions: requirements
  clarification, architecture planning, code generation for both backend and frontend, test
  authoring, running the test suite, and fixing bugs it found in its own output.
- **Grok (xAI, `grok-4`)** — integrated *into the product* as the `LLMService` in
  `backend/app/llm/service.py`, used at runtime for admin-tooling features (NL rule authoring,
  cold-start suggestions, post-save product suggestions, ruleset review).
- **Gemini embeddings** (session 2) — integrated as `EmbeddingService` in
  `backend/app/embeddings/service.py`, used at runtime for the purchase-history similarity rail, via
  a FAISS index in `backend/app/embeddings/index.py`.

## 2. Key prompts / interaction flow

The build wasn't one long prompt — it was iterative, with the user actively steering:

1. Initial ask: "understand this problem statement and explain it... we also need a UI."
   → Claude explained the abstract requirements and proposed a generic rules-engine deliverable.
2. User rejected the generic direction mid-plan: *"suggest me where we can integrate LLM in this
   project"* and, before that, pivoted the entire domain: *"what we are thinking for e-commerce
   domain — admin panel where admin can change rules... user page... recommended products."*
   → Claude re-planned around a concrete e-commerce recommendation engine instead of an abstract
   demo (loan/insurance rules), since a judged demo needs a visible product.
3. User specified the LLM provider explicitly: *"make sure we are planning to use grok api"* and
   requested specific features: NL rule authoring, cold-start fallback, a rule-creation feedback
   loop ("if not found any product acc to the rule suggest them either add product... or change
   your rule"), and a live preview ("based on the selected rule, the recommendation component is
   changed").
   → Claude folded all four into the plan with a shared `LLMService` abstraction and deterministic
   fallbacks, rather than hard-wiring Grok calls inline.
4. Before finalizing, the user asked Claude to self-critique: *"suggest what we can improve... is
   this aligned with the problem statement."*
   → Claude produced a requirement-by-requirement alignment table, identified low-cost
   "twist-proofing" additions (audit retrieval, a `version` field, bulk evaluation), and explicitly
   called out scope risks (shopper UI is the most time-expensive, non-graded part) before asking the
   user to confirm scope trade-offs via structured questions rather than guessing.

## 3. AI-generated code that was accepted as-is

- The full operator registry (`engine/operators.py`) and recursive condition evaluator
  (`engine/condition_evaluator.py`) — generated in one pass and passed all unit tests immediately.
- The `RuleRepository` file-backed implementation with YAML read/write round-tripping.
- All FastAPI route modules, Pydantic schemas, and the exception-handler wiring in `main.py`.
- The full React admin (`RulesAdminPage.tsx`, `RuleForm.tsx`) and shopper pages — accepted after a
  successful `tsc --noEmit` and `npm run build` with zero errors.

## 4. AI-generated code that was rejected or modified

- **First engine plan was too abstract.** The initial plan targeted a generic loan/insurance
  decision engine. The user rejected this direction (see prompt 2 above) before any code was
  written, redirecting to the e-commerce recommendation framing — caught at the planning stage, so
  no code needed to be thrown away.
- **`rule_admin_service.update_rule` used `model_copy(update=payload.model_dump())`.** This dumped
  nested `Condition`/`RecommendAction` objects into plain dicts and reassigned them onto typed
  fields without re-validating, which Pydantic surfaced as a serializer warning during testing
  (`Expected 'Condition' but got 'dict'`). Fixed by re-validating through `Rule.model_validate()` on
  a merged dict instead of `model_copy`.
- **`FileRuleRepository.reorder` allowed partial id lists**, silently leaving unrelated rules with
  stale priorities (a real correctness bug, not just a lint issue — see next section).

## 5. How AI outputs were validated

- **41 pytest tests** were written alongside the implementation (not after), covering: every
  operator, nested AND/OR/NOT condition trees, rule-engine priority ordering, both decision
  strategies, file-repository read/write/versioning round-trips, the recommendation service for all
  three shopping flows plus cold-start fallback and bulk evaluation, and end-to-end API tests via
  `TestClient` (with the Grok client forced onto its deterministic fallback path so tests run
  offline).
- **Manual `curl` verification** of every endpoint against a live running instance (not just the
  test suite) — home/search/purchase/bulk recommendations, NL rule generation, rule preview,
  cold-start fallback, and CORS behavior from the frontend's origin were all exercised directly.
- **Frontend**: `tsc --noEmit` and `npm run build` were run to catch type errors; both dev servers
  were started and the backend was hit with requests carrying the frontend's `Origin` header to
  confirm CORS actually works end-to-end (no browser-automation tool was available in this
  environment to do a literal click-through, so this was disclosed rather than assumed correct).

## 6. Bugs introduced by AI and how they were resolved

1. **Reorder logic bug**: `RuleRepository.reorder(ordered_ids)` initially accepted a *partial* list
   of rule ids and only reassigned priorities among those, leaving the rest of the ruleset with
   unchanged (often higher) priorities — so reordering 3 of 11 rules didn't actually move them to
   the top of the full list, contradicting the obvious intent of a "reorder" operation. Caught by a
   test (`test_reorder_rules_via_api`) that reordered a partial list and asserted the wrong thing
   first, which led to inspecting the *repository* logic rather than just fixing the test — the fix
   was to make `reorder` require a full permutation of every existing rule id (422 otherwise),
   matching how a real drag-to-reorder admin table would call it, and updating both the repository
   test and the API test to reflect the corrected contract.
2. **Pydantic serializer warning on rule update** (described in §4) — caught by `pytest -q` output
   (warnings are not silent in this suite), fixed by switching from `model_copy(update=...)` to a
   dict-merge + `model_validate()`, which properly re-hydrates nested `Condition`/`RecommendAction`
   objects instead of leaving raw dicts on a typed field.

No other functional bugs surfaced during manual endpoint verification; the remaining test failures
during development were the two above, both fixed in the same session before moving on.

## Session 2 — making AI load-bearing, not decorative

The first session's own docstrings admitted the gap: `recommendation_service.py` said
"Recommendations are rule-based only (no LLM/AI involvement)." Every AI touchpoint was an optional
admin convenience with a deterministic fallback — fine for reliability, but it meant the core
decision path had zero AI dependency. This session's brief, driven by the user across several
turns, was to fix that without weakening the rule engine's explainability, which is the platform's
actual deliverable per the problem statement.

### 1. Key prompts / interaction flow
1. User asked whether the e-commerce domain and current implementation actually fit the problem
   statement, given the hackathon is judged on AI-engineering criteria (a rubric image was shared:
   30% weight on "AI is load-bearing... not decorated with it"). → Claude audited the codebase
   directly (reading `recommendation_service.py`, `llm/service.py`) rather than assuming, and
   reported the gap plainly instead of overstating existing AI usage.
2. User proposed replacing self-reported `interests` with purchase-history-derived signal, then
   proposed making the **entire** Recommendation rail LLM-driven. → Claude pushed back on the
   second part specifically: an LLM's self-reported reason for a choice is not guaranteed to be the
   actual cause (a known interpretability problem), and replacing the rule engine would break the
   golden-set-testability and the `rules_evaluated/matched/rejected` trace the whole platform is
   built around. Landed on: rule engine stays deterministic; embeddings live in a genuinely
   different, additive mechanism (the purchase-history rail).
3. User chose FAISS + Gemini embeddings specifically (over TF-IDF or an OpenAI-compatible generic
   embedding call that had been proposed first) — a self-contained decision, not something Claude
   needed to argue for.
4. User asked to unify the NL-rule-authoring flow with preview, since having the LLM draft a rule
   and only previewing match count *after* saving made the LLM authorship path feel less trustworthy
   than it needed to be.
5. Before implementing, Claude used the Plan-mode workflow (explore → design → `ExitPlanMode`) to
   get explicit sign-off on: the embeddings provider (external API vs. local model vs. TF-IDF), the
   shopper-identification approach (anonymous localStorage id vs. a demo-persona switcher), and the
   scope boundary for this pass (core personalization rework only — eval harness/RAG/multi-agent
   authoring explicitly deferred) — all three were genuine judgment calls, not things to guess.

### 2. AI-generated code accepted as-is
- `PurchaseHistoryRepository` (ABC + JSON-backed impl) — deliberately mirrors `FileRuleRepository`'s
  `threading.RLock` + load/persist pattern already in the codebase; no changes needed.
- `EmbeddingService` ABC + `GeminiEmbeddingService` — mirrors `LLMService`'s fallback discipline.
- The rules-YAML rename (`interests` → `purchase_tags`) — mechanical, verified against
  `products.json` first (rule values match `Product.tags`, not `Product.category` — confirmed
  before renaming, not assumed).

### 3. AI-generated code that was rejected or modified
- **First cut of `similar_to_purchases` re-embedded every candidate product per request** via
  `embed_query()`, even though those products were already in the FAISS index. Caught during
  implementation review (not by a test) — refactored `ProductVectorIndex` to cache each product's
  vector in a `dict[product_id, vector]` alongside the FAISS index and added `get_vector()`, so
  ranking a shopper's neighbors costs zero additional embedding calls after the index is built once.
- **First cut of the FAISS index build had no guard against a mid-batch API failure.** If Gemini
  embeds some products successfully then fails partway through, the partial batch would mix
  768-dim real vectors with 256-dim fallback vectors, silently corrupting the vector space (or
  crashing `np.array`). Fixed by detecting a dimension mismatch and rebuilding the *entire* index
  with fallback vectors for consistency, rather than embedding "as much as possible."
- **`_DEFAULT_PREVIEW_PROFILE` in `rule_admin_service.py` still passed `interests=[...]`** to the
  `Profile` constructor after the field was removed from the schema — would have raised a Pydantic
  validation error on the first admin-preview call. Caught by re-reading the file before editing it
  (not by running the app first), fixed by removing the field and adding a separate
  `_DEFAULT_PREVIEW_PURCHASE_TAGS` constant injected directly into preview facts.

### 4. How AI outputs were validated
- **55 pytest tests** (up from 41) — new files `test_purchase_history_repository.py` and
  `test_embeddings.py`, plus every existing test that constructed `Profile(interests=...)` or posted
  `{"interests": [...]}` was rewritten against the new `purchase_tags`/`shopper_id` contract (not
  left passing against a stale assumption).
- **Manual end-to-end smoke test against a live `uvicorn` instance**, not just unit tests: a cold
  shopper hitting the new catch-all rule, buying a product, confirming `purchase_history.json`
  persisted it, confirming the next `/recommend/home` call reflected the derived `purchase_tags`,
  confirming `/recommend/similar` excluded the just-bought item and cited it as the similarity
  reason, and confirming `/rules/preview-draft` resolves matches without writing to the ruleset.
  Test-shopper data written during this smoke test was then cleaned out of the seed file before
  finishing, since it wasn't meant to ship.
- `tsc -b` run clean on the frontend after all `Profile`/`client.ts`/admin-page changes.

### 5. Bugs introduced by AI and how they were resolved
1. **Redundant embedding calls** (see §3) — an efficiency bug, not a correctness one, but worth
   listing since "how does this scale" is exactly the kind of question this fix pre-empts.
2. **Mixed-dimension vector space on partial API failure** (see §3) — a real correctness bug that
   would only surface intermittently (only when Gemini fails mid-batch), which is precisely the
   kind of bug that's easy to miss without deliberately reasoning about the failure mode rather than
   just the happy path.
3. **Stale `interests=[...]` construction in the admin preview default profile** (see §3) — a
   straightforward miss from removing a field in one file without grepping for every construction
   site; caught before running anything by re-reading the file first.

## Session 3 — RAG, persistent embeddings, a real multi-agent pipeline, and a provider mix-up

The user asked directly why rule authoring didn't use RAG or multi-agent orchestration and where
embeddings were actually stored, given the stated goal of making the platform genuinely AI-heavy.
The honest answer: neither had been built — both were explicitly deferred to a later pass at the end
of session 2, and the FAISS product index was in-memory only, re-embedded from scratch every process
restart. This session built both, live-tested every new piece against real Gemini/Groq API calls
(not just the offline fallback path), and found three real bugs doing so.

### Key prompts / interaction flow
1. User: *"is it applying rag like saving the rule and check the rule against other rule and also
   where we are storing the embedding data as I cannot see any storage for embeddings"* → Claude
   audited the actual code rather than assuming, confirmed both gaps directly (no RAG on save, no
   persisted index — the FAISS index lives in `lru_cache`d process memory only), and named the one
   existing partial mechanism (the manual, non-RAG "Review ruleset" button) precisely so as not to
   overstate what existed.
2. User: *"why we are not using embedding, rag and multi agents"* → Claude proposed a concrete
   architecture (persist the product index; a separate, non-persisted `RuleVectorIndex` for RAG,
   since rules mutate constantly and the catalog doesn't; a five-step pipeline — Interpret → Retrieve
   → Conflict-check → Validate/repair → Preview) rather than treating "add RAG and multi-agent" as
   self-explanatory, then planned it formally (Plan mode: explore → design → user approval) before
   writing code, same discipline as session 2's larger rework.
3. During implementation, live `curl` testing against the user's real Gemini key surfaced two
   provider-level bugs (below) that no amount of code review would have caught, since both only
   manifest against a live API. After fixing them, the user said *"use GROQ_API_KEY"* — the .env
   file's key was for Groq, not xAI's Grok, despite the settings field being named `xai_api_key`; the
   provider had silently never been live in sessions 1-2, always falling through to the offline
   fallback. Claude verified the correct base URL, model name, and endpoint shape against the real
   key (`api.groq.com/openai/v1`, `llama-3.3-70b-versatile`) before renaming `GrokLLMService` →
   `GroqLLMService` and every associated field/env-var/doc reference, rather than guessing.

### AI-generated code accepted as-is
- `PurchaseHistoryRepository`-style persistence pattern reused for `ProductVectorIndex.save()`/load —
  FAISS binary + a JSON sidecar (product-id order + source), invalidated by comparing the sidecar's
  id list against the live catalog.
- The five-step pipeline structure in `RuleAdminService.draft_rule_with_pipeline` — each step as a
  `PipelineStep(agent, status, detail)`, letting the admin UI render an inspectable trace instead of
  one opaque result.

### AI-generated code that was rejected or modified
- **First cut of `similar_to_purchases` re-embedded already-indexed products per request** instead
  of reading their vectors back out of the built index — fixed by adding `get_vector()` (session 2,
  caught before this session, listed here as it's the same class of mistake avoided this time).
- **First cut of persistence stored un-normalized vectors from a fresh build, but normalized vectors
  from a disk reload** (`index.reconstruct()` returns the normalized copy actually indexed) — the
  "nearest purchased product" citation logic would have ranked differently before vs. after a
  restart. Caught by re-reading the diff before running anything, not by a test; fixed by storing
  the normalized `matrix` values consistently in both code paths.
- **First cut of `embed`/`embed_batch` used the default Gemini model name `text-embedding-004`**,
  which doesn't exist for this API version — confirmed via `ListModels` and corrected to
  `gemini-embedding-001` before writing a single line of dependent code, exactly the "verify against
  the real key" discipline the previous session's mistakes argued for.

### How AI outputs were validated
- **74 pytest tests** (up from 61) — new files for the rule-vector index, conflict-check heuristic,
  and embedding persistence round-trip (save → new instance → load → assert vectors match without a
  second embed call).
- **Live end-to-end verification against real provider APIs**, not just the offline fallback:
  - `curl` to Gemini's real `embedContent`/`batchEmbedContents`/`ListModels` endpoints directly (bypassing the app) to diagnose the 404 before touching code.
  - Two full `uvicorn` process restarts to confirm the persisted index actually loads from disk
    (log line asserted, not assumed) instead of re-embedding.
  - `/rules/draft-with-review` exercised with three cases: a draft textually close to an existing
    rule (confirmed RAG retrieval + conflict flag naming the specific rule), a novel draft (confirmed
    verdict `"ok"`), and rubbish text (confirmed the pipeline stops after the Interpreter step rather
    than running Retrieve/Conflict-check/Validate against nothing).
  - `curl` directly against `api.groq.com` with the real key before renaming anything, so the
    `GroqLLMService` rename was verified working, not just compiling.

### Bugs found and how they were resolved
1. **Wrong default Gemini embedding model name** (`text-embedding-004`, doesn't exist for v1beta) —
   found because the *first* live embeddings call in this session's testing 404'd; fixed by querying
   `ListModels` for the real value instead of guessing again.
2. **256 sequential embedding HTTP calls on first build** (~3.5 minutes blocking startup latency) —
   found by a `curl` call timing out during manual verification; fixed by adding a real
   `embed_batch()` using Gemini's `batchEmbedContents` endpoint (verified to exist and work before
   relying on it), cutting ~256 calls to ~6.
3. **Vector-normalization inconsistency between a fresh build and a disk-loaded index** (see above) —
   found by re-reading the persistence diff, not by a failing test; a case where the test suite
   passing was not sufficient evidence of correctness, and manual reasoning about the two code paths
   was what actually caught it.
4. **Provider name/config mismatch**: the app was built and documented as using Grok (xAI), but the
   only real key ever configured was for Groq — meaning the "real LLM" path had silently never run in
   sessions 1-2; every prior claim of Grok being exercised live was actually the offline fallback.
   Not a code bug, but a configuration/naming trap worth recording: a plausible-sounding, similarly-
   named provider silently masked that the live path was never tested until this session's direct
   `curl` verification forced the question.
