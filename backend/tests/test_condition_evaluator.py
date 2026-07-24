from app.engine.condition_evaluator import evaluate_condition
from app.models.schemas import Condition


def test_leaf_match():
    cond = Condition(field="age", operator="gte", value=18)
    matched, reason = evaluate_condition(cond, {"age": 25})
    assert matched
    assert "age=25" in reason


def test_leaf_no_match():
    cond = Condition(field="age", operator="gte", value=18)
    matched, _ = evaluate_condition(cond, {"age": 10})
    assert not matched


def test_all_group():
    cond = Condition(
        all=[
            Condition(field="age", operator="gte", value=18),
            Condition(field="budget_band", operator="equals_ci", value="high"),
        ]
    )
    assert evaluate_condition(cond, {"age": 30, "budget_band": "HIGH"})[0]
    assert not evaluate_condition(cond, {"age": 30, "budget_band": "low"})[0]


def test_any_group():
    cond = Condition(
        any=[
            Condition(field="interests", operator="any_in", value=["gaming"]),
            Condition(field="interests", operator="any_in", value=["music"]),
        ]
    )
    assert evaluate_condition(cond, {"interests": ["music", "travel"]})[0]
    assert not evaluate_condition(cond, {"interests": ["sports"]})[0]


def test_not_group():
    cond = Condition(not_=Condition(field="gender", operator="equals_ci", value="male"))
    assert evaluate_condition(cond, {"gender": "female"})[0]
    assert not evaluate_condition(cond, {"gender": "male"})[0]


def test_missing_field_is_falsey():
    cond = Condition(field="age", operator="gt", value=18)
    assert not evaluate_condition(cond, {})[0]


def test_nested_tree():
    cond = Condition(
        all=[
            Condition(field="interests", operator="any_in", value=["gaming"]),
            Condition(
                any=[
                    Condition(field="max_budget", operator="gte", value=1000),
                    Condition(field="budget_band", operator="equals_ci", value="high"),
                ]
            ),
        ]
    )
    assert evaluate_condition(cond, {"interests": ["gaming"], "budget_band": "high"})[0]
    assert not evaluate_condition(cond, {"interests": ["gaming"], "budget_band": "low"})[0]
