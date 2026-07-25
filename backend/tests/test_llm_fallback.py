from app.llm import fallback


def test_nl_to_rule_returns_none_for_rubbish_text():
    assert fallback.nl_to_rule("zzzqwe asdkj not a real request", categories=[], tags=[]) is None


def test_nl_to_rule_returns_none_for_unsupported_signal():
    # "location" isn't in the currently supported scope (purchase history/interest, budget) —
    # must say so rather than default to a fabricated interest like "gaming".
    assert fallback.nl_to_rule("recommend rain jackets to people in Seattle", categories=[], tags=[]) is None


def test_nl_to_rule_does_not_false_positive_on_substring_tags():
    # "seat" is a real catalog tag and a literal substring of "Seattle" — naive
    # substring matching would wrongly treat this as a confident "seat" match.
    rule = fallback.nl_to_rule(
        "recommend rain jackets to people who live in Seattle", categories=[], tags=["seat"]
    )
    assert rule is None


def test_nl_to_rule_matches_known_interest_keyword():
    rule = fallback.nl_to_rule("recommend gear for gaming", categories=[], tags=[])
    assert rule is not None
    assert rule["condition"] == {"field": "purchase_tags", "operator": "any_in", "value": ["gaming"]}


def test_nl_to_rule_matches_budget_keyword():
    rule = fallback.nl_to_rule("show cheap products", categories=[], tags=[])
    assert rule is not None
    assert rule["condition"]["field"] == "budget_band"


def test_check_rule_conflicts_flags_overlapping_condition():
    draft = {"condition": {"field": "purchase_tags", "operator": "any_in", "value": ["beauty"]}}
    candidates = [
        {
            "id": "rule-beauty",
            "condition": {"field": "purchase_tags", "operator": "any_in", "value": ["beauty", "skincare"]},
        }
    ]
    result = fallback.check_rule_conflicts(draft, candidates)
    assert result["verdict"] == "overlap"
    assert result["candidates"][0]["rule_id"] == "rule-beauty"


def test_check_rule_conflicts_ok_for_unrelated_rules():
    draft = {"condition": {"field": "purchase_tags", "operator": "any_in", "value": ["travel"]}}
    candidates = [
        {"id": "rule-beauty", "condition": {"field": "purchase_tags", "operator": "any_in", "value": ["beauty"]}}
    ]
    result = fallback.check_rule_conflicts(draft, candidates)
    assert result["verdict"] == "ok"
    assert result["candidates"] == []


def test_check_rule_conflicts_ignores_different_fields():
    draft = {"condition": {"field": "purchase_tags", "operator": "any_in", "value": ["beauty"]}}
    candidates = [{"id": "rule-x", "condition": {"field": "budget_band", "operator": "equals_ci", "value": "beauty"}}]
    result = fallback.check_rule_conflicts(draft, candidates)
    assert result["verdict"] == "ok"


def test_repair_rule_returns_none_offline():
    assert fallback.repair_rule({"name": "broken"}, "some validation error") is None
