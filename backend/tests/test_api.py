import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


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
    resp = client.post("/recommend/home", json={"profile": {"interests": ["gaming"], "budget_band": "high", "max_budget": 2000}})
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
    resp = client.post("/evaluate", json={"context_type": "home", "facts": {"interests": ["gaming"]}})
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
        json={"profiles": [{"interests": ["gaming"]}, {"interests": ["beauty"]}]},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_product_not_found_returns_404(client):
    resp = client.get("/products/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "ProductNotFoundError"
