from app.engine.decision_strategies import Contribution, get_strategy
from app.engine.rule_engine import evaluate_rules
from app.models.schemas import Condition, RecommendAction, Rule


def _rule(rid, priority, field, op, value, enabled=True, score=1.0):
    return Rule(
        id=rid,
        name=rid,
        priority=priority,
        enabled=enabled,
        condition=Condition(field=field, operator=op, value=value),
        recommend=RecommendAction(products=[f"p-{rid}"], score=score),
    )


def test_engine_partitions_matched_and_rejected():
    rules = [
        _rule("a", 10, "age", "gte", 18),
        _rule("b", 20, "age", "lt", 18),
    ]
    result = evaluate_rules(rules, {"age": 25})
    assert result.rules_evaluated == 2
    matched_ids = {t.rule_id for t in result.matched}
    rejected_ids = {t.rule_id for t in result.rejected}
    assert matched_ids == {"a"}
    assert rejected_ids == {"b"}


def test_engine_orders_by_priority_desc():
    rules = [
        _rule("low", 1, "age", "gte", 0),
        _rule("high", 100, "age", "gte", 0),
    ]
    result = evaluate_rules(rules, {"age": 5})
    assert [t.rule_id for t in result.matched] == ["high", "low"]


def test_engine_skips_disabled_rules():
    rules = [_rule("off", 10, "age", "gte", 0, enabled=False)]
    result = evaluate_rules(rules, {"age": 5})
    assert result.rules_evaluated == 0


def test_weighted_strategy_sums_scores():
    contributions = [
        Contribution("p1", 2.0, "r1"),
        Contribution("p1", 1.0, "r2"),
        Contribution("p2", 5.0, "r3"),
    ]
    ranked = get_strategy("weighted_score")(contributions)
    assert ranked[0].product_id == "p2"
    p1 = next(a for a in ranked if a.product_id == "p1")
    assert p1.score == 3.0
    assert set(p1.rule_ids) == {"r1", "r2"}


def test_max_strategy_takes_strongest():
    contributions = [Contribution("p1", 2.0, "r1"), Contribution("p1", 5.0, "r2")]
    ranked = get_strategy("max_score")(contributions)
    assert ranked[0].score == 5.0
