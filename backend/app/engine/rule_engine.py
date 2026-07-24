"""Core rule engine: evaluate all rules against facts, produce match traces.

The engine is domain-agnostic. It knows nothing about products or profiles — it
only evaluates conditions and reports which rules matched and why. Higher-level
services turn the matched rules' `recommend` actions into concrete outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.engine.condition_evaluator import evaluate_condition
from app.models.schemas import Rule, RuleTrace

logger = get_logger(__name__)


@dataclass
class EngineResult:
    rules_evaluated: int = 0
    matched: list[RuleTrace] = field(default_factory=list)
    rejected: list[RuleTrace] = field(default_factory=list)


def evaluate_rules(rules: list[Rule], facts: dict) -> EngineResult:
    """Run every enabled rule (highest priority first) against the facts."""
    result = EngineResult()
    ordered = sorted(
        (r for r in rules if r.enabled), key=lambda r: r.priority, reverse=True
    )
    for rule in ordered:
        result.rules_evaluated += 1
        matched, reason = evaluate_condition(rule.condition, facts)
        trace = RuleTrace(
            rule_id=rule.id,
            rule_name=rule.name,
            priority=rule.priority,
            matched=matched,
            reason=reason,
            recommend=rule.recommend,
        )
        if matched:
            result.matched.append(trace)
        else:
            result.rejected.append(trace)
    logger.debug(
        "evaluated %d rules: %d matched, %d rejected",
        result.rules_evaluated,
        len(result.matched),
        len(result.rejected),
    )
    return result
