# API Reference

Base URL: `http://localhost:8000`. Interactive Swagger UI at `/docs`, OpenAPI schema at `/openapi.json`.
All errors return `{"error": "<ExceptionClass>", "message": "..."}` with the matching HTTP status
(404 not found, 422 validation, 502 upstream LLM failure).

## Health

`GET /health` → `{"status": "ok"}`

## Catalog

`GET /products?category=<optional>` → `Product[]`
`GET /products/{product_id}` → `Product` (404 if missing)

## Recommendations (the decision engine, e-commerce-flavored)

`interests` is not a client-supplied field — no real shopper self-reports interests. Every
`profile`-shaped request instead takes a `shopper_id`; the server derives an interest signal
(`purchase_tags`) server-side from that shopper's actual purchase history (`app/history/`) and
feeds it into the rule engine. A shopper with no purchase history yet gets `purchase_tags: []`.

### `POST /recommend/home`
```json
{ "profile": { "budget_band": "high", "max_budget": 2000 }, "shopper_id": "shopper-demo-gamer" }
```
→ `Decision` (see shape below).

### `POST /recommend/search`
```json
{ "profile": {}, "shopper_id": "shopper-demo-gamer", "search_query": "laptop", "search_category": null }
```

### `POST /recommend/purchase`
```json
{ "profile": {}, "shopper_id": "shopper-demo-gamer", "purchased_product_id": "p009" }
```
Also persists the purchase to `PurchaseHistoryRepository` — the next `/recommend/home` call for the
same `shopper_id` reflects it in `purchase_tags`.

### `POST /recommend/bulk`
```json
{ "profiles": [ { "budget_band": "high" }, { "budget_band": "low" } ] }
```
→ `Decision[]` — one per profile. Bulk is a batch what-if analysis, not tied to an individual
shopper, so each profile evaluates cold-start (`purchase_tags: []`).

### `POST /recommend/similar`
```json
{ "shopper_id": "shopper-demo-gamer" }
```
→
```json
{
  "items": [
    {
      "product": { "id": "p043", "name": "Nova Studio", "...": "..." },
      "score": 0.57,
      "similar_to_product_id": "p001",
      "reason": "Similar to your purchase of 'Nova Gaming Laptop 15'"
    }
  ],
  "source": "gemini"
}
```
The purchase-history rail — a genuinely different mechanism from the rest of `/recommend/*`:
embeddings (Gemini, with a deterministic offline fallback when `GEMINI_API_KEY` is unset) + a FAISS
similarity search over the catalog, ranked by cosine similarity to the shopper's past purchases.
Deliberately **not** a `Decision` — there is no rule trace to report, only a similarity score, so
diluting the rule engine's explainability shape with a different mechanism would be misleading.
Returns `items: []` for a shopper with no purchase history.

### `Decision` response shape
```json
{
  "decision_id": "uuid",
  "context_type": "home",
  "context": { "...facts used for evaluation..." },
  "recommendations": [
    {
      "product": { "id": "p001", "name": "...", "category": "...", "price": 1499.0, "tags": [...] },
      "score": 8.0,
      "matched_rule_ids": ["rule-gaming-laptop", "rule-gaming-gear"],
      "reason": "Recommended because: ...",
      "source": "rules"
    }
  ],
  "rules_evaluated": 11,
  "rules_matched": [ { "rule_id": "...", "rule_name": "...", "priority": 100, "matched": true, "reason": "..." } ],
  "rules_rejected": [ { "rule_id": "...", "matched": false, "reason": "age=15 did not match 'gte' 18" } ],
  "explanation": "11 rule(s) evaluated; 2 matched (...); results ranked by aggregated rule score.",
  "used_ai_fallback": false,
  "created_at": "2026-07-24T08:29:01Z"
}
```

## Raw engine access / audit

### `POST /evaluate`
Pass any facts dict directly (bypasses the profile-shaped helpers above):
```json
{ "context_type": "home", "facts": { "purchase_tags": ["gaming"], "budget_band": "high" } }
```

### `GET /decisions?limit=50`
Returns the most recent recorded decisions (audit history).

### `GET /decisions/{decision_id}`
Retrieve one past decision by id (404 if not found/expired from memory).

## Rule administration

### `GET /rules` → `Rule[]` (sorted by priority desc)
### `GET /rules/{rule_id}` → `Rule` (404 if missing)

### `POST /rules` — create
```json
{
  "name": "High-budget gamer -> gaming laptop",
  "description": "",
  "enabled": true,
  "priority": 100,
  "condition": {
    "all": [
      { "field": "purchase_tags", "operator": "any_in", "value": ["gaming"] },
      { "field": "max_budget", "operator": "gte", "value": 1000 }
    ]
  },
  "recommend": { "products": ["p001"], "categories": [], "tags": ["gaming"], "score": 5 }
}
```
→ `Rule` (id auto-generated, version=1).

### `PUT /rules/{rule_id}` — update (same body as create)
→ `Rule` with `version` incremented and `updated_at` refreshed.

### `DELETE /rules/{rule_id}` → `{"status": "deleted", "rule_id": "..."}`

### `PATCH /rules/reorder`
```json
{ "ordered_ids": ["rule-a", "rule-b", "rule-c"] }
```
Must include **every** existing rule id exactly once (422 otherwise) — priorities are reassigned
descending in the given order.

## AI (Groq)-backed endpoints

All degrade to a deterministic offline fallback if `GROQ_API_KEY` is unset or the Groq call fails —
responses include a `source: "groq" | "fallback"` field so callers can tell which path was used.

### `POST /rules/from-text`
```json
{ "text": "Recommend gaming accessories to users interested in gaming who search for a laptop" }
```
→ `{ "rule": <RuleCreate>, "source": "groq", "notes": "..." }` — not saved automatically; the admin
reviews/edits before `POST /rules`.

### `POST /rules/{rule_id}/preview`
```json
{ "profile": { "budget_band": "high" } }
```
(`profile` optional — a demo profile with representative `purchase_tags` is used if omitted.)
→
```json
{
  "rule_id": "rule-gaming-laptop",
  "matched": true,
  "matched_products": [ { "id": "p001", "name": "..." } ],
  "feedback": "This rule currently resolves to 6 product(s): ...",
  "needs_product": false,
  "suggested_product": null
}
```
When `matched_products` is empty, `needs_product: true` and `suggested_product` holds a
Groq-suggested product spec to add to the catalog.

### `POST /rules/preview-draft`
Same response shape as `/rules/{rule_id}/preview`, but for an **unsaved** draft rule — body is a
`RuleCreate` (no `id` yet). Lets the admin see the match count *before* committing, instead of
generate → save → preview-after-the-fact. This is what fuses NL rule authoring and preview into one
step in the admin UI: after `/rules/from-text` returns a draft, the UI immediately calls this
endpoint and shows the match count inline in the same modal.
```json
{
  "name": "Draft rule", "priority": 10,
  "condition": { "field": "purchase_tags", "operator": "any_in", "value": ["gaming"] },
  "recommend": { "tags": ["gaming"], "score": 1.0 }
}
```
→ `rule_id: "draft"` in the response; nothing is written to the ruleset.

### `POST /rules/review`
No body. → `{ "review": "...bullet-point findings...", "source": "groq" }`.

### `POST /rules/draft-with-review`
The rule-authoring pipeline in one call: **Interpret → Retrieve (RAG over the existing ruleset) →
Conflict-check → Validate/repair → Preview**. Fuses `/rules/from-text` + a RAG conflict-check +
`/rules/preview-draft` into a single round trip, with every step recorded so the admin can see what
happened rather than getting one opaque result.
```json
{ "text": "recommend skincare to beauty shoppers" }
```
→
```json
{
  "rule": { "name": "...", "condition": { "...": "..." }, "recommend": { "...": "..." } },
  "conflict_check": {
    "verdict": "overlap",
    "candidates": [
      { "rule_id": "rule-beauty", "rule_name": "Beauty interest -> skincare", "similarity": 0.62,
        "note": "same field 'purchase_tags', overlapping value(s): ['beauty']" }
    ],
    "notes": "1 retrieved rule(s) share the same condition field and an overlapping value.",
    "source": "groq"
  },
  "preview": { "rule_id": "draft", "matched": false, "matched_products": [ "...": "..." ], "...": "..." },
  "steps": [
    { "agent": "Interpreter", "status": "ok", "detail": "drafted via groq" },
    { "agent": "Retriever", "status": "ok", "detail": "found 3 similar existing rule(s)" },
    { "agent": "Conflict-checker", "status": "ok", "detail": "verdict=overlap via groq" },
    { "agent": "Validator", "status": "ok", "detail": "" },
    { "agent": "Previewer", "status": "ok", "detail": "This rule currently resolves to 10 product(s): ..." }
  ],
  "source": "groq",
  "notes": "Generated via groq"
}
```
`conflict_check.verdict` **warns, it never blocks** — saving is still a separate, explicit
`POST /rules` / `PUT /rules/{id}` call. Retrieval finding zero similar rules skips the
conflict-check LLM call entirely (`conflict_check.source: "none"`) rather than paying for a call
with nothing to compare against. If the Interpreter step reports the request as unsupported (see
`/rules/from-text` above), `rule`/`conflict_check`/`preview` are all `null` and `steps` has only the
one Interpreter entry.
