"""Orchestrates: build context -> run rule engine -> resolve products -> rank -> explain.

This is the one place that turns generic rule matches into concrete e-commerce
recommendations. Recommendations are rule-based only (no LLM/AI involvement) and
every outcome is recorded to the audit store.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.catalog.repository import ProductRepository
from app.core.exceptions import ProductNotFoundError
from app.core.logging import get_logger
from app.engine.decision_strategies import Contribution, get_strategy
from app.engine.rule_engine import evaluate_rules
from app.models.schemas import (
    Decision,
    Product,
    Profile,
    RecommendedProduct,
    Rule,
)
from app.rules.repository import RuleRepository
from app.services.audit_store import AuditStore

logger = get_logger(__name__)

DEFAULT_LIMIT = 8
DEFAULT_STRATEGY = "weighted_score"


def resolve_recommend_targets(recommend, product_repo: ProductRepository) -> list[Product]:
    """Turn a rule's recommend action (ids/categories/tags) into concrete products."""
    found: dict[str, Product] = {}
    for pid in recommend.products:
        try:
            p = product_repo.get(pid)
            found[p.id] = p
        except ProductNotFoundError:
            continue
    for category in recommend.categories:
        for p in product_repo.by_category(category):
            found[p.id] = p
    for tag in recommend.tags:
        for p in product_repo.by_tag(tag):
            found[p.id] = p
    return list(found.values())


class RecommendationService:
    def __init__(
        self,
        rule_repo: RuleRepository,
        product_repo: ProductRepository,
        audit_store: AuditStore,
    ):
        self.rule_repo = rule_repo
        self.product_repo = product_repo
        self.audit_store = audit_store

    # ------------------------------------------------------------------ #
    def _build_decision(
        self,
        context_type: str,
        facts: dict[str, Any],
        limit: int = DEFAULT_LIMIT,
        exclude_product_ids: set[str] | None = None,
    ) -> Decision:
        exclude_product_ids = exclude_product_ids or set()
        logger.info("building decision: context=%s facts=%s", context_type, facts)
        rules = self.rule_repo.list_rules()
        result = evaluate_rules(rules, facts)
        logger.info(
            "rule evaluation: %d evaluated, %d matched, %d rejected",
            result.rules_evaluated,
            len(result.matched),
            len(result.rejected),
        )

        contributions: list[Contribution] = []
        rule_recommend_by_id: dict[str, Rule] = {r.id: r for r in rules}
        product_by_rule: dict[str, list[Product]] = {}
        for trace in result.matched:
            rule = rule_recommend_by_id[trace.rule_id]
            products = resolve_recommend_targets(rule.recommend, self.product_repo)
            product_by_rule[rule.id] = products
            for p in products:
                if p.id in exclude_product_ids:
                    continue
                contributions.append(Contribution(product_id=p.id, score=rule.recommend.score, rule_id=rule.id))

        if exclude_product_ids:
            logger.info("excluding already-purchased product(s) from suggestions: %s", exclude_product_ids)

        aggregated = get_strategy(DEFAULT_STRATEGY)(contributions)
        recommendations = [
            RecommendedProduct(
                product=self.product_repo.get(agg.product_id),
                score=agg.score,
                matched_rule_ids=agg.rule_ids,
                reason="Recommended because: "
                + "; ".join(
                    next(t.reason for t in result.matched if t.rule_id == rid) for rid in agg.rule_ids
                ),
                source="rules",
            )
            for agg in aggregated[:limit]
        ]

        explanation = self._explain(result.rules_evaluated, result.matched)
        logger.info("decision built: %d recommendation(s) for context=%s", len(recommendations), context_type)

        decision = Decision(
            decision_id=str(uuid.uuid4()),
            context_type=context_type,
            context=facts,
            recommendations=recommendations,
            rules_evaluated=result.rules_evaluated,
            rules_matched=result.matched,
            rules_rejected=result.rejected,
            explanation=explanation,
            used_ai_fallback=False,
        )
        return self.audit_store.record(decision)

    @staticmethod
    def _explain(evaluated: int, matched) -> str:
        if not matched:
            return f"{evaluated} rule(s) evaluated; none matched this shopper, so no rule-based recommendations are available."
        names = ", ".join(f"'{t.rule_name}'" for t in matched) or "none"
        return f"{evaluated} rule(s) evaluated; {len(matched)} matched ({names}); results ranked by aggregated rule score."

    # ------------------------------------------------------------------ #
    def home(self, profile: Profile, limit: int = DEFAULT_LIMIT) -> Decision:
        logger.info("home recommendation requested: interests=%s", profile.interests)
        facts = profile.model_dump()
        facts["context_type"] = "home"
        return self._build_decision("home", facts, limit)

    def search(self, profile: Profile, search_query: str, search_category: str | None, limit: int = DEFAULT_LIMIT) -> Decision:
        logger.info("search recommendation requested: query=%r category=%s", search_query, search_category)
        facts = profile.model_dump()
        facts.update(context_type="search", search_query=search_query, search_category=search_category)
        return self._build_decision("search", facts, limit)

    def purchase(self, profile: Profile, purchased_product_id: str, limit: int = DEFAULT_LIMIT) -> Decision:
        product = self.product_repo.get(purchased_product_id)
        logger.info("purchase recommendation requested: purchased_product_id=%s", purchased_product_id)
        facts = profile.model_dump()
        facts.update(
            context_type="purchase",
            purchased_product_id=purchased_product_id,
            purchased_category=product.category,
            purchased_tags=product.tags,
        )
        # Never suggest back the product the shopper just bought.
        return self._build_decision("purchase", facts, limit, exclude_product_ids={purchased_product_id})

    def evaluate(self, facts: dict[str, Any], limit: int = DEFAULT_LIMIT) -> Decision:
        return self._build_decision(facts.get("context_type", "evaluate"), facts, limit)

    def bulk(self, profiles: list[Profile], limit: int = DEFAULT_LIMIT) -> list[Decision]:
        return [self.home(p, limit) for p in profiles]
