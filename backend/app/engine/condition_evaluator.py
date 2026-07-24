"""Evaluate a recursive Condition tree against a flat facts dict.

Returns (matched, reason) so the engine can explain *why* a rule fired or not.
Field lookups support dotted paths (e.g. "profile.age") but flat keys are typical.
"""
from __future__ import annotations

from typing import Any

from app.engine.operators import get_operator
from app.models.schemas import Condition


def _resolve(facts: dict[str, Any], field: str) -> Any:
    value: Any = facts
    for part in field.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def evaluate_condition(condition: Condition, facts: dict[str, Any]) -> tuple[bool, str]:
    if condition.all is not None:
        results = [evaluate_condition(c, facts) for c in condition.all]
        matched = all(r[0] for r in results)
        if matched:
            return True, "all conditions passed"
        failed = next(r[1] for r in results if not r[0])
        return False, f"failed AND: {failed}"

    if condition.any is not None:
        results = [evaluate_condition(c, facts) for c in condition.any]
        matched = any(r[0] for r in results)
        if matched:
            passed = next(r[1] for r in results if r[0])
            return True, f"matched OR: {passed}"
        return False, "no OR branch matched"

    if condition.not_ is not None:
        inner_matched, inner_reason = evaluate_condition(condition.not_, facts)
        return (not inner_matched), f"NOT ({inner_reason})"

    # leaf
    actual = _resolve(facts, condition.field)
    op = get_operator(condition.operator)
    matched = op(actual, condition.value)
    verb = "matched" if matched else "did not match"
    reason = (
        f"{condition.field}={actual!r} {verb} '{condition.operator}' {condition.value!r}"
    )
    return matched, reason
