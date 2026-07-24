from app.models.schemas import Profile
from tests.conftest import SHOPPER_BEAUTY, SHOPPER_COLD, SHOPPER_FITNESS


def test_home_recommends_fitness_products_for_shopper_with_fitness_history(recommendation_service):
    profile = Profile(budget_band="high", max_budget=2000)
    decision = recommendation_service.home(profile, SHOPPER_FITNESS)
    assert decision.rules_evaluated > 0
    assert any(t.rule_id == "rule-fitness" for t in decision.rules_matched)
    product_ids = {r.product.id for r in decision.recommendations}
    assert "p014" in product_ids  # FlexFit Yoga Mat, category=fitness
    assert not decision.used_ai_fallback


def test_search_surfaces_rule_matched_products_for_shopper_with_beauty_history(recommendation_service):
    profile = Profile()
    decision = recommendation_service.search(profile, SHOPPER_BEAUTY, search_query="skincare", search_category=None)
    assert any(t.rule_id == "rule-beauty" for t in decision.rules_matched)
    product_ids = {r.product.id for r in decision.recommendations}
    assert "p018" in product_ids  # Aurora Daily Moisturizer, tag=beauty
    assert all(r.source == "rules" for r in decision.recommendations)


def test_purchase_excludes_the_purchased_product_itself(recommendation_service):
    # p017 is tagged beauty/skincare; rule-beauty recommends beauty-tagged
    # products, which would include p017 itself without exclusion.
    profile = Profile()
    decision = recommendation_service.purchase(profile, "shopper-fresh-buyer", purchased_product_id="p017")
    product_ids = {r.product.id for r in decision.recommendations}
    assert "p017" not in product_ids
    assert any(t.rule_id == "rule-beauty" for t in decision.rules_matched)


def test_purchase_persists_to_history(recommendation_service):
    recommendation_service.purchase(Profile(), "shopper-persist-test", purchased_product_id="p013")
    assert recommendation_service.purchase_history_repo.get("shopper-persist-test") == ["p013"]


def test_cold_start_shopper_still_gets_catch_all_recommendation(recommendation_service):
    """No purchase history -> purchase_tags == [] -> every tag-based rule
    rejects, but the catch-all rule (no purchase_tags dependency) guarantees
    the Recommendation rail is never empty — no AI involved."""
    profile = Profile()
    decision = recommendation_service.home(profile, SHOPPER_COLD)
    assert not decision.used_ai_fallback
    assert any(t.rule_id == "rule-catch-all-trending" for t in decision.rules_matched)
    assert decision.recommendations
    assert all(r.source == "rules" for r in decision.recommendations)


def test_bulk_returns_one_decision_per_profile(recommendation_service):
    profiles = [Profile(budget_band="high"), Profile(budget_band="low")]
    decisions = recommendation_service.bulk(profiles)
    assert len(decisions) == 2


def test_decision_is_recorded_in_audit_store(recommendation_service):
    profile = Profile()
    decision = recommendation_service.home(profile, SHOPPER_FITNESS)
    fetched = recommendation_service.audit_store.get(decision.decision_id)
    assert fetched.decision_id == decision.decision_id


def test_similar_to_purchases_excludes_already_purchased(recommendation_service):
    resp = recommendation_service.similar_to_purchases(SHOPPER_FITNESS)
    ids = {item.product.id for item in resp.items}
    assert "p013" not in ids


def test_similar_to_purchases_empty_for_shopper_with_no_history(recommendation_service):
    resp = recommendation_service.similar_to_purchases(SHOPPER_COLD)
    assert resp.items == []
