"""Pluggable decision-aggregation strategies.

A strategy takes the per-product score contributions produced by matched rules and
decides the final ranked list. Adding a new strategy = one function + registration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.core.exceptions import RuleValidationError


@dataclass
class Contribution:
    product_id: str
    score: float
    rule_id: str


@dataclass
class AggregatedProduct:
    product_id: str
    score: float
    rule_ids: list[str] = field(default_factory=list)


StrategyFn = Callable[[list[Contribution]], list[AggregatedProduct]]

_STRATEGIES: dict[str, StrategyFn] = {}


def strategy(name: str) -> Callable[[StrategyFn], StrategyFn]:
    def deco(fn: StrategyFn) -> StrategyFn:
        _STRATEGIES[name] = fn
        return fn

    return deco


def get_strategy(name: str) -> StrategyFn:
    if name not in _STRATEGIES:
        raise RuleValidationError(
            f"unknown strategy '{name}'. available: {sorted(_STRATEGIES)}"
        )
    return _STRATEGIES[name]


def _group(contributions: list[Contribution]) -> dict[str, AggregatedProduct]:
    grouped: dict[str, AggregatedProduct] = {}
    for c in contributions:
        agg = grouped.setdefault(c.product_id, AggregatedProduct(product_id=c.product_id, score=0.0))
        if c.rule_id not in agg.rule_ids:
            agg.rule_ids.append(c.rule_id)
        agg.score += c.score
    return grouped


@strategy("weighted_score")
def weighted_score(contributions: list[Contribution]) -> list[AggregatedProduct]:
    """Sum every matched rule's score per product; rank highest first."""
    grouped = _group(contributions)
    return sorted(grouped.values(), key=lambda a: a.score, reverse=True)


@strategy("max_score")
def max_score(contributions: list[Contribution]) -> list[AggregatedProduct]:
    """Score = the single strongest rule that recommends the product."""
    grouped: dict[str, AggregatedProduct] = {}
    for c in contributions:
        agg = grouped.setdefault(c.product_id, AggregatedProduct(product_id=c.product_id, score=0.0))
        if c.rule_id not in agg.rule_ids:
            agg.rule_ids.append(c.rule_id)
        agg.score = max(agg.score, c.score)
    return sorted(grouped.values(), key=lambda a: a.score, reverse=True)
