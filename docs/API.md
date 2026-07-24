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

### `POST /recommend/home`
```json
{ "profile": { "interests": ["gaming"], "budget_band": "high", "max_budget": 2000 } }
```
→ `Decision` (see shape below).

### `POST /recommend/search`
```json
{ "profile": { "interests": [] }, "search_query": "laptop", "search_category": null }
```

### `POST /recommend/purchase`
```json
{ "profile": { "interests": [] }, "purchased_product_id": "p009" }
```

### `POST /recommend/bulk`
```json
{ "profiles": [ { "interests": ["gaming"] }, { "interests": ["beauty"] } ] }
```
→ `Decision[]` — one per profile.

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
{ "context_type": "home", "facts": { "interests": ["gaming"], "budget_band": "high" } }
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
      { "field": "interests", "operator": "any_in", "value": ["gaming"] },
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

## AI (Grok)-backed endpoints

All degrade to a deterministic offline fallback if `XAI_API_KEY` is unset or the Grok call fails —
responses include a `source: "grok" | "fallback"` field so callers can tell which path was used.

### `POST /rules/from-text`
```json
{ "text": "Recommend gaming accessories to users interested in gaming who search for a laptop" }
```
→ `{ "rule": <RuleCreate>, "source": "grok", "notes": "..." }` — not saved automatically; the admin
reviews/edits before `POST /rules`.

### `POST /rules/{rule_id}/preview`
```json
{ "profile": { "interests": ["gaming"], "budget_band": "high" } }
```
(`profile` optional — a demo profile is used if omitted.)
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
Grok-suggested product spec to add to the catalog.

### `POST /rules/review`
No body. → `{ "review": "...bullet-point findings...", "source": "grok" }`.
