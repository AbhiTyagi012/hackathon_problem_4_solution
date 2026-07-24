"""Operator registry — the primary extensibility point of the engine.

To add a new comparison type, write a pure function ``(actual, expected) -> bool``
and register it with ``@operator("name")``. No other file needs to change.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable

from app.core.exceptions import RuleValidationError

OperatorFn = Callable[[Any, Any], bool]

_REGISTRY: dict[str, OperatorFn] = {}


def operator(name: str) -> Callable[[OperatorFn], OperatorFn]:
    def deco(fn: OperatorFn) -> OperatorFn:
        _REGISTRY[name] = fn
        return fn

    return deco


def get_operator(name: str) -> OperatorFn:
    if name not in _REGISTRY:
        raise RuleValidationError(
            f"unknown operator '{name}'. available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def available_operators() -> list[str]:
    return sorted(_REGISTRY)


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise RuleValidationError(f"cannot interpret {value!r} as a date")


# --- numeric / generic comparisons ---------------------------------------- #
@operator("eq")
def _eq(actual: Any, expected: Any) -> bool:
    return actual == expected


@operator("ne")
def _ne(actual: Any, expected: Any) -> bool:
    return actual != expected


@operator("gt")
def _gt(actual: Any, expected: Any) -> bool:
    return actual is not None and actual > expected


@operator("gte")
def _gte(actual: Any, expected: Any) -> bool:
    return actual is not None and actual >= expected


@operator("lt")
def _lt(actual: Any, expected: Any) -> bool:
    return actual is not None and actual < expected


@operator("lte")
def _lte(actual: Any, expected: Any) -> bool:
    return actual is not None and actual <= expected


@operator("between")
def _between(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, (list, tuple)) or len(expected) != 2:
        raise RuleValidationError("'between' expects a [min, max] value")
    low, high = expected
    return actual is not None and low <= actual <= high


# --- boolean --------------------------------------------------------------- #
@operator("is_true")
def _is_true(actual: Any, expected: Any) -> bool:
    return bool(actual) is True


@operator("is_false")
def _is_false(actual: Any, expected: Any) -> bool:
    return bool(actual) is False


# --- string ---------------------------------------------------------------- #
@operator("contains")
def _contains(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    return str(expected).lower() in str(actual).lower()


@operator("equals_ci")
def _equals_ci(actual: Any, expected: Any) -> bool:
    return actual is not None and str(actual).lower() == str(expected).lower()


@operator("starts_with")
def _starts_with(actual: Any, expected: Any) -> bool:
    return actual is not None and str(actual).lower().startswith(str(expected).lower())


@operator("regex")
def _regex(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    return re.search(str(expected), str(actual)) is not None


# --- membership (works with list fields like interests) -------------------- #
@operator("in")
def _in(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, (list, tuple, set)):
        raise RuleValidationError("'in' expects a list value")
    return actual in expected


@operator("not_in")
def _not_in(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, (list, tuple, set)):
        raise RuleValidationError("'not_in' expects a list value")
    return actual not in expected


@operator("any_in")
def _any_in(actual: Any, expected: Any) -> bool:
    """True if the actual list shares any element with the expected list."""
    actual_set = set(actual) if isinstance(actual, (list, tuple, set)) else {actual}
    expected_set = set(expected) if isinstance(expected, (list, tuple, set)) else {expected}
    return bool(actual_set & expected_set)


@operator("all_in")
def _all_in(actual: Any, expected: Any) -> bool:
    actual_set = set(actual) if isinstance(actual, (list, tuple, set)) else {actual}
    expected_set = set(expected) if isinstance(expected, (list, tuple, set)) else {expected}
    return expected_set.issubset(actual_set)


# --- existence ------------------------------------------------------------- #
@operator("exists")
def _exists(actual: Any, expected: Any) -> bool:
    present = actual is not None
    return present if bool(expected) else not present


# --- dates ----------------------------------------------------------------- #
@operator("date_before")
def _date_before(actual: Any, expected: Any) -> bool:
    return _to_date(actual) < _to_date(expected)


@operator("date_after")
def _date_after(actual: Any, expected: Any) -> bool:
    return _to_date(actual) > _to_date(expected)
