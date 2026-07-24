import pytest

from app.core.exceptions import RuleValidationError
from app.engine.operators import available_operators, get_operator


def test_numeric_operators():
    assert get_operator("gt")(10, 5)
    assert not get_operator("gt")(5, 10)
    assert get_operator("gte")(5, 5)
    assert get_operator("lt")(3, 5)
    assert get_operator("lte")(5, 5)
    assert get_operator("between")(5, [1, 10])
    assert not get_operator("between")(50, [1, 10])


def test_equality_and_boolean():
    assert get_operator("eq")("a", "a")
    assert get_operator("ne")("a", "b")
    assert get_operator("is_true")(True, None)
    assert get_operator("is_false")(False, None)


def test_string_operators():
    assert get_operator("contains")("Gaming Laptop", "laptop")
    assert get_operator("equals_ci")("HIGH", "high")
    assert get_operator("starts_with")("electronics", "elec")
    assert get_operator("regex")("SKU-123", r"SKU-\d+")


def test_membership_operators():
    assert get_operator("in")("gaming", ["gaming", "music"])
    assert get_operator("not_in")("sports", ["gaming", "music"])
    assert get_operator("any_in")(["gaming", "travel"], ["gaming", "music"])
    assert not get_operator("any_in")(["sports"], ["gaming", "music"])
    assert get_operator("all_in")(["gaming", "music", "travel"], ["gaming", "music"])


def test_exists_operator():
    assert get_operator("exists")("value", True)
    assert get_operator("exists")(None, False)
    assert not get_operator("exists")(None, True)


def test_date_operators():
    assert get_operator("date_before")("2020-01-01", "2021-01-01")
    assert get_operator("date_after")("2022-01-01", "2021-01-01")


def test_unknown_operator_raises():
    with pytest.raises(RuleValidationError):
        get_operator("does_not_exist")


def test_registry_lists_operators():
    ops = available_operators()
    assert "gt" in ops and "any_in" in ops and "regex" in ops
