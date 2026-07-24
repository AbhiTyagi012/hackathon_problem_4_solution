"""Orchestrates: build context -> run rule engine -> resolve products -> rank -> explain.

This is the one place that turns generic rule matches into concrete e-commerce
recommendations. The Recommendation rail stays rule-based only (no LLM/AI
involvement) so its rule-trace explainability is never diluted — but the facts
it evaluates against now include `purchase_tags`, derived server-side from the
shopper's actual purchase history instead of a self-reported interests field.

The purchase-history similarity rail (`similar_to_purchases`) is a genuinely
different, embeddings-based mechanism — deliberately not folded into Decision,
since it has no rule trace to report.

Every rule-based outcome is recorded to the audit store.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.catalog.repository import ProductRepository
from app.core.exceptions import ProductNotFoundError
from app.core.logging import get_logger
from app.embeddings.index import ProductVectorIndex, product_text
from app.engine.decision_strategies import AggregatedProduct, Contribution, get_strategy
from app.engine.rule_engine import evaluate_rules
from app.history.repository import PurchaseHistoryRepository
from app.models.schemas import (
    Decision,
    Product,
    Profile,
    RecommendedProduct,
    Rule,
    SimilarProduct,
    SimilarProductsResponse,
)
from app.rules.repository import RuleRepository
from app.services.audit_store import AuditStore

logger = get_logger(__name__)

DEFAULT_LIMIT = 8
DEFAULT_STRATEGY = "weighted_score"


def _diversify_by_rule(aggregated: list[AggregatedProduct], limit: int) -> list[AggregatedProduct]:
    """Round-robin the score-sorted, per-product aggregates across the rules that
    contributed them, capped at ``limit``.

    A flat top-N slice lets ties in score get broken by insertion order, so
    whichever rule's products were aggregated first fills every slot — a rule
    that legitimately matched can end up with none of its products visible just
    because other matched rules were processed earlier. Round-robining by
    contributing rule guarantees every matched rule gets a fair share.
    """
    buckets: dict[str, list[AggregatedProduct]] = {}
    order: list[str] = []
    for agg in aggregated:  # already sorted by score desc
        primary_rule = agg.rule_ids[0]
        if primary_rule not in buckets:
            buckets[primary_rule] = []
            order.append(primary_rule)
        buckets[primary_rule].append(agg)

    selected: list[AggregatedProduct] = []
    while len(selected) < limit and any(buckets[r] for r in order):
        for r in order:
            if buckets[r]:
                selected.append(buckets[r].pop(0))
                if len(selected) >= limit:
                    break
    return selected


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
        purchase_history_repo: PurchaseHistoryRepository,
        vector_index: ProductVectorIndex,
    ):
        self.rule_repo = rule_repo
        self.product_repo = product_repo
        self.audit_store = audit_store
        self.purchase_history_repo = purchase_history_repo
        self.vector_index = vector_index

    # ------------------------------------------------------------------ #
    def _purchase_tags(self, shopper_id: str) -> list[str]:
        """Derive an interest signal from what the shopper has actually bought,
        instead of a self-reported field. Tags (not category) are the right
        granularity: rule values like 'gaming'/'beauty' match Product.tags,
        while Product.category is coarser ('laptops', 'electronics')."""
        tags: set[str] = set()
        for product_id in self.purchase_history_repo.get(shopper_id):
            try:
                tags.update(self.product_repo.get(product_id).tags)
            except ProductNotFoundError:
                continue
        return sorted(tags)

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
            for agg in _diversify_by_rule(aggregated, limit)
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
    def home(self, profile: Profile, shopper_id: str, limit: int = DEFAULT_LIMIT) -> Decision:
        purchase_tags = self._purchase_tags(shopper_id)
        logger.info("home recommendation requested: shopper=%s purchase_tags=%s", shopper_id, purchase_tags)
        facts = profile.model_dump()
        facts.update(context_type="home", purchase_tags=purchase_tags)
        return self._build_decision("home", facts, limit)

    def search(
        self, profile: Profile, shopper_id: str, search_query: str, search_category: str | None, limit: int = DEFAULT_LIMIT
    ) -> Decision:
        logger.info("search recommendation requested: query=%r category=%s", search_query, search_category)
        facts = profile.model_dump()
        facts.update(
            context_type="search",
            purchase_tags=self._purchase_tags(shopper_id),
            search_query=search_query,
            search_category=search_category,
        )
        return self._build_decision("search", facts, limit)

    def purchase(self, profile: Profile, shopper_id: str, purchased_product_id: str, limit: int = DEFAULT_LIMIT) -> Decision:
        product = self.product_repo.get(purchased_product_id)
        logger.info("purchase recommendation requested: shopper=%s purchased_product_id=%s", shopper_id, purchased_product_id)
        self.purchase_history_repo.record_purchase(shopper_id, purchased_product_id)
        facts = profile.model_dump()
        facts.update(
            context_type="purchase",
            purchase_tags=self._purchase_tags(shopper_id),
            purchased_product_id=purchased_product_id,
            purchased_category=product.category,
            purchased_tags=product.tags,
        )
        # Never suggest back the product the shopper just bought.
        return self._build_decision("purchase", facts, limit, exclude_product_ids={purchased_product_id})

    def evaluate(self, facts: dict[str, Any], limit: int = DEFAULT_LIMIT) -> Decision:
        return self._build_decision(facts.get("context_type", "evaluate"), facts, limit)

    def bulk(self, profiles: list[Profile], limit: int = DEFAULT_LIMIT) -> list[Decision]:
        # Bulk is a batch what-if analysis, not tied to an individual shopper's
        # purchase history, so each profile evaluates cold-start (purchase_tags=[]).
        return [self.home(p, shopper_id="", limit=limit) for p in profiles]

    def similar_to_purchases(self, shopper_id: str, limit: int = DEFAULT_LIMIT) -> SimilarProductsResponse:
        """Purchase-history rail: embeddings + cosine similarity, not rule-based.

        Deliberately separate from the rule-engine's Decision/RuleTrace shape —
        there is no rule trace here, only a similarity score.
        """
        purchased_ids = self.purchase_history_repo.get(shopper_id)
        if not purchased_ids:
            return SimilarProductsResponse(items=[], source="fallback")

        purchased_products: list[Product] = []
        for pid in purchased_ids:
            try:
                purchased_products.append(self.product_repo.get(pid))
            except ProductNotFoundError:
                continue
        if not purchased_products:
            return SimilarProductsResponse(items=[], source="fallback")

        # get_vector reads the already-built catalog index — no re-embedding at request time.
        purchased_vectors = [(p, self.vector_index.get_vector(p.id)) for p in purchased_products]
        purchased_vectors = [(p, v) for p, v in purchased_vectors if v is not None]
        avg_vector = [sum(dim) / len(purchased_vectors) for dim in zip(*(v for _, v in purchased_vectors))]
        neighbors = self.vector_index.search(avg_vector, limit, exclude_ids=set(purchased_ids))

        # Cite the single nearest purchased product per result, by name, as the reason.
        items: list[SimilarProduct] = []
        for product_id, score in neighbors:
            candidate_vec = self.vector_index.get_vector(product_id)
            nearest = max(
                purchased_vectors,
                key=lambda pv: sum(a * b for a, b in zip(pv[1], candidate_vec)),
            )[0]
            items.append(
                SimilarProduct(
                    product=self.product_repo.get(product_id),
                    score=score,
                    similar_to_product_id=nearest.id,
                    reason=f"Similar to your purchase of '{nearest.name}'",
                )
            )
        return SimilarProductsResponse(items=items, source=self.vector_index.source)
