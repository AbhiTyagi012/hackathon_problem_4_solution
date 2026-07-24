# AI Engineering Log

This entire project was built in a single session using **Claude Code** (Anthropic's agentic CLI,
running Claude Sonnet 5) as the sole development tool — planning, code generation, test writing,
and debugging. The product itself additionally integrates the **Grok (xAI) API** as a runtime
feature (NL→rule authoring, cold-start recommendations, ruleset review) — that is a feature of the
shipped app, not a build-tool; it's documented separately in the README under "AI (Grok) features."

## 1. AI tools used

- **Claude Code (Sonnet 5)** — used for the entire SDLC: requirements clarification, architecture
  planning, code generation for both backend and frontend, test authoring, running the test suite,
  and fixing bugs it found in its own output.
- **Grok (xAI, `grok-4`)** — integrated *into the product* as the `LLMService` in
  `backend/app/llm/service.py`, used at runtime for the four AI-assisted admin/shopper features.

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
