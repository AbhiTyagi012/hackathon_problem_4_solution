from app.models.schemas import Profile


def test_home_recommends_gaming_products_for_gamer(recommendation_service):
    profile = Profile(interests=["gaming"], budget_band="high", max_budget=2000)
    decision = recommendation_service.home(profile)
    assert decision.rules_evaluated > 0
    assert any(r.matched for r in decision.rules_matched) or decision.rules_matched
    product_ids = {r.product.id for r in decision.recommendations}
    assert "p001" in product_ids  # gaming laptop
    assert not decision.used_ai_fallback


def test_search_surfaces_rule_matched_products_for_gamer(recommendation_service):
    profile = Profile(interests=["gaming"])
    decision = recommendation_service.search(profile, search_query="looking for a laptop", search_category=None)
    product_ids = {r.product.id for r in decision.recommendations}
    assert {"p004", "p005", "p006"} & product_ids
    assert all(r.source == "rules" for r in decision.recommendations)


def test_purchase_excludes_the_purchased_product_itself(recommendation_service):
    # p001 is a gaming laptop; the "gaming interest" rule recommends its own
    # category/tags, so without exclusion it would suggest itself back.
    profile = Profile(interests=["gaming"], budget_band="high", max_budget=2000)
    decision = recommendation_service.purchase(profile, purchased_product_id="p001")
    product_ids = {r.product.id for r in decision.recommendations}
    assert "p001" not in product_ids


def test_cold_start_returns_no_recommendations_without_ai(recommendation_service):
    profile = Profile(interests=["extremely-niche-hobby-xyz"])
    decision = recommendation_service.home(profile)
    assert not decision.used_ai_fallback
    assert decision.recommendations == []
    assert all(r.source == "rules" for r in decision.recommendations)


def test_bulk_returns_one_decision_per_profile(recommendation_service):
    profiles = [Profile(interests=["gaming"]), Profile(interests=["beauty"])]
    decisions = recommendation_service.bulk(profiles)
    assert len(decisions) == 2


def test_decision_is_recorded_in_audit_store(recommendation_service):
    profile = Profile(interests=["gaming"])
    decision = recommendation_service.home(profile)
    fetched = recommendation_service.audit_store.get(decision.decision_id)
    assert fetched.decision_id == decision.decision_id
