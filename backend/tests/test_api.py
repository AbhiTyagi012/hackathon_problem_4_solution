import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from tests.conftest import SHOPPER_FITNESS


@pytest.fixture
def client(rule_repo, product_repo, llm_service, recommendation_service, rule_admin_service):
    app.dependency_overrides[deps.get_rule_repository] = lambda: rule_repo
    app.dependency_overrides[deps.get_product_repository] = lambda: product_repo
    app.dependency_overrides[deps.get_llm_service] = lambda: llm_service
    app.dependency_overrides[deps.get_audit_store] = lambda: recommendation_service.audit_store
    app.dependency_overrides[deps.get_recommendation_service] = lambda: recommendation_service
    app.dependency_overrides[deps.get_rule_admin_service] = lambda: rule_admin_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_list_rules(client):
    resp = client.get("/rules")
    assert resp.status_code == 200
    assert len(resp.json()) >= 10


def test_recommend_home_returns_ranked_products_with_explanation(client):
    resp = client.post(
        "/recommend/home",
        json={"profile": {"budget_band": "high", "max_budget": 2000}, "shopper_id": SHOPPER_FITNESS},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendations"]
    assert body["explanation"]
    assert body["rules_matched"]


def test_create_update_delete_rule_via_api(client):
    payload = {
        "name": "API test rule",
        "priority": 42,
        "condition": {"field": "budget_band", "operator": "equals_ci", "value": "medium"},
        "recommend": {"categories": ["home"], "score": 1.5},
    }
    created = client.post("/rules", json=payload)
    assert created.status_code == 200
    rule_id = created.json()["id"]

    fetched = client.get(f"/rules/{rule_id}")
    assert fetched.status_code == 200
    assert fetched.json()["priority"] == 42

    payload["priority"] = 55
    updated = client.put(f"/rules/{rule_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["priority"] == 55
    assert updated.json()["version"] == 2

    deleted = client.delete(f"/rules/{rule_id}")
    assert deleted.status_code == 200
    assert client.get(f"/rules/{rule_id}").status_code == 404


def test_create_rule_blocks_on_conflict_with_existing_rule(client):
    """Same field + overlapping value as the seeded rule-beauty should be
    blocked (409) rather than silently saved — that's the actual enforcement
    point, not just the optional NL-preview pipeline."""
    payload = {
        "name": "Duplicate beauty rule",
        "priority": 50,
        "condition": {"field": "purchase_tags", "operator": "any_in", "value": ["beauty"]},
        "recommend": {"tags": ["beauty"], "score": 1.0},
    }
    resp = client.post("/rules", json=payload)
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "RuleConflictError"
    assert body["detail"]["verdict"] != "ok"
    assert any(c["rule_id"] == "rule-beauty" for c in body["detail"]["candidates"])


def test_create_rule_succeeds_with_confirm_conflict(client):
    payload = {
        "name": "Duplicate beauty rule, confirmed",
        "priority": 50,
        "condition": {"field": "purchase_tags", "operator": "any_in", "value": ["beauty"]},
        "recommend": {"tags": ["beauty"], "score": 1.0},
        "confirm_conflict": True,
    }
    resp = client.post("/rules", json=payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Duplicate beauty rule, confirmed"


def test_update_rule_does_not_block_against_itself(client):
    """Editing a rule (e.g. just its priority) must not be blocked by RAG
    retrieving the rule's own prior version as a 'conflict'."""
    rules = client.get("/rules").json()
    beauty = next(r for r in rules if r["id"] == "rule-beauty")
    payload = {
        "name": beauty["name"],
        "priority": 71,
        "condition": beauty["condition"],
        "recommend": beauty["recommend"],
    }
    resp = client.put(f"/rules/{beauty['id']}", json=payload)
    assert resp.status_code == 200
    assert resp.json()["priority"] == 71


def test_reorder_rules_via_api(client):
    ids = [r["id"] for r in client.get("/rules").json()]
    shuffled = ids[::-1]
    reordered = client.patch("/rules/reorder", json={"ordered_ids": shuffled})
    assert reordered.status_code == 200
    assert [r["id"] for r in reordered.json()] == shuffled


def test_rule_from_text_endpoint(client):
    resp = client.post("/rules/from-text", json={"text": "recommend audio products to music lovers"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rule"]["condition"]


def test_rule_from_text_rejects_unsupported_text_instead_of_guessing(client):
    """Rubbish text (or a request depending on an unsupported signal, e.g.
    location) must not silently fabricate a plausible-looking rule."""
    resp = client.post("/rules/from-text", json={"text": "asdkj qwoie zzz not a real request"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rule"] is None
    assert "supported" in body["notes"].lower()


def test_draft_with_review_flags_conflict_with_similar_existing_rule(client):
    """A draft textually close to the seeded rule-beauty should retrieve it via
    RAG and get flagged by the offline conflict-check heuristic."""
    resp = client.post("/rules/draft-with-review", json={"text": "recommend skincare to beauty shoppers"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rule"] is not None
    assert body["conflict_check"] is not None
    assert body["conflict_check"]["verdict"] == "overlap"
    assert any(c["rule_id"] == "rule-beauty" for c in body["conflict_check"]["candidates"])
    agents = [s["agent"] for s in body["steps"]]
    assert agents == ["Interpreter", "Retriever", "Conflict-checker", "Validator", "Previewer"]
    assert body["preview"] is not None


def test_draft_with_review_unsupported_text_stops_after_interpreter(client):
    resp = client.post("/rules/draft-with-review", json={"text": "asdkj qwoie zzz not a real request"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rule"] is None
    assert body["conflict_check"] is None
    assert [s["agent"] for s in body["steps"]] == ["Interpreter"]
    assert body["steps"][0]["status"] == "unsupported"


def test_rule_preview_no_match_suggests_product(client):
    payload = {
        "name": "Impossible rule",
        "priority": 10,
        "condition": {"field": "age", "operator": "eq", "value": 999},
        "recommend": {"categories": ["nonexistent-category"], "score": 1.0},
    }
    rule_id = client.post("/rules", json=payload).json()["id"]
    preview = client.post(f"/rules/{rule_id}/preview", json={})
    assert preview.status_code == 200
    body = preview.json()
    assert body["needs_product"] is True
    assert body["suggested_product"]


def test_evaluate_and_decision_retrieval(client):
    resp = client.post("/evaluate", json={"context_type": "home", "facts": {"purchase_tags": ["beauty"]}})
    assert resp.status_code == 200
    decision_id = resp.json()["decision_id"]

    fetched = client.get(f"/decisions/{decision_id}")
    assert fetched.status_code == 200

    listed = client.get("/decisions")
    assert listed.status_code == 200
    assert any(d["decision_id"] == decision_id for d in listed.json())


def test_bulk_recommend_endpoint(client):
    resp = client.post(
        "/recommend/bulk",
        json={"profiles": [{"budget_band": "high"}, {"budget_band": "low"}]},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_preview_draft_rule_endpoint(client):
    payload = {
        "name": "Draft rule",
        "priority": 10,
        "condition": {"field": "budget_band", "operator": "equals_ci", "value": "medium"},
        "recommend": {"categories": ["home"], "score": 1.0},
    }
    resp = client.post("/rules/preview-draft", json=payload)
    assert resp.status_code == 200
    assert resp.json()["rule_id"] == "draft"


def test_recommend_similar_endpoint(client):
    resp = client.post("/recommend/similar", json={"shopper_id": SHOPPER_FITNESS})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "p013" not in {item["product"]["id"] for item in body["items"]}


def test_product_not_found_returns_404(client):
    resp = client.get("/products/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "ProductNotFoundError"
