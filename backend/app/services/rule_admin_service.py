"""Admin-facing rule management: CRUD, reorder, NL authoring, preview, and the
post-save catalog-match feedback loop backed by Grok."""
from __future__ import annotations

import json
import re
import uuid

from app.catalog.repository import ProductRepository
from app.core.exceptions import RuleValidationError
from app.core.logging import get_logger
from app.engine.condition_evaluator import evaluate_condition
from app.engine.operators import available_operators
from app.llm.service import LLMService
from app.models.schemas import (
    Condition,
    NlRuleResponse,
    Profile,
    Rule,
    RuleCreate,
    RulePreviewResponse,
    RuleReviewResponse,
)
from app.rules.repository import RuleRepository
from app.services.recommendation_service import resolve_recommend_targets

logger = get_logger(__name__)

_DEFAULT_PREVIEW_PROFILE = Profile(
    age=28,
    gender="unspecified",
    budget_band="high",
    max_budget=1500,
    location="unspecified",
)
# Admin preview has no real shopper/purchase history to derive purchase_tags
# from, so it uses a representative sample — enough to exercise most rules
# without wiring a shopper_id through the admin tooling.
_DEFAULT_PREVIEW_PURCHASE_TAGS = ["gaming", "music"]


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "rule"
    return f"{base}-{uuid.uuid4().hex[:6]}"


class RuleAdminService:
    def __init__(self, rule_repo: RuleRepository, product_repo: ProductRepository, llm_service: LLMService):
        self.rule_repo = rule_repo
        self.product_repo = product_repo
        self.llm_service = llm_service

    # -- CRUD --------------------------------------------------------------- #
    def list_rules(self) -> list[Rule]:
        return self.rule_repo.list_rules()

    def get_rule(self, rule_id: str) -> Rule:
        return self.rule_repo.get(rule_id)

    def create_rule(self, payload: RuleCreate) -> Rule:
        rule = Rule(id=_slugify(payload.name), **payload.model_dump())
        created = self.rule_repo.add(rule)
        logger.info("rule created: id=%s name=%r priority=%d", created.id, created.name, created.priority)
        return created

    def update_rule(self, rule_id: str, payload: RuleCreate) -> Rule:
        existing = self.rule_repo.get(rule_id)
        merged = {**existing.model_dump(), **payload.model_dump()}
        updated = Rule.model_validate(merged)
        saved = self.rule_repo.update(updated)
        logger.info("rule updated: id=%s name=%r version=%d", saved.id, saved.name, saved.version)
        return saved

    def delete_rule(self, rule_id: str) -> None:
        self.rule_repo.delete(rule_id)
        logger.info("rule deleted: id=%s", rule_id)

    def reorder(self, ordered_ids: list[str]) -> list[Rule]:
        reordered = self.rule_repo.reorder(ordered_ids)
        logger.info("rules reordered: %s", ordered_ids)
        return reordered

    # -- Grok-backed features ------------------------------------------------ #
    def nl_to_rule(self, text: str) -> NlRuleResponse:
        categories = self.product_repo.categories()
        tags = self.product_repo.tags()
        data, source = self.llm_service.nl_to_rule(text, available_operators(), categories, tags)
        try:
            rule_create = RuleCreate.model_validate(data)
        except Exception as exc:
            logger.error("nl_to_rule produced an invalid rule from text %r: %s", text, exc)
            raise RuleValidationError(f"AI produced an invalid rule: {exc}") from exc
        logger.info("rule drafted from text via %s: %r", source, rule_create.name)
        return NlRuleResponse(rule=rule_create, source=source, notes=f"Generated via {source}")

    def preview(self, rule_id: str, profile: Profile | None) -> RulePreviewResponse:
        rule = self.rule_repo.get(rule_id)
        return self._preview(rule_id, rule.condition, rule.recommend, profile, json.loads(rule.model_dump_json()))

    def preview_draft(self, payload: RuleCreate, profile: Profile | None) -> RulePreviewResponse:
        """Same evaluation as preview(), but for an unsaved draft rule — lets the
        admin see match count *before* committing (fuses NL-drafting + preview
        into one step instead of generate -> save -> preview-after-the-fact)."""
        return self._preview("draft", payload.condition, payload.recommend, profile, payload.model_dump())

    def _preview(
        self, rule_id: str, condition: Condition, recommend, profile: Profile | None, rule_for_llm: dict
    ) -> RulePreviewResponse:
        facts = (profile or _DEFAULT_PREVIEW_PROFILE).model_dump()
        facts["context_type"] = "home"
        facts["purchase_tags"] = _DEFAULT_PREVIEW_PURCHASE_TAGS
        matched, _ = evaluate_condition(condition, facts)
        products = resolve_recommend_targets(recommend, self.product_repo)
        logger.info("rule preview: id=%s matched=%s resolved_products=%d", rule_id, matched, len(products))

        if products:
            feedback = (
                f"This rule currently resolves to {len(products)} product(s): "
                + ", ".join(p.name for p in products[:5])
                + ("…" if len(products) > 5 else "")
            )
            return RulePreviewResponse(
                rule_id=rule_id, matched=matched, matched_products=products, feedback=feedback
            )

        suggestion, source = self.llm_service.suggest_product_for_rule(
            rule_for_llm, self.product_repo.categories(), self.product_repo.tags()
        )
        logger.info("rule preview: id=%s has no matching product, suggested one via %s", rule_id, source)
        feedback = (
            "No catalog product matches this rule's recommend targets yet. "
            f"Either add a matching product (suggested via {source}: "
            f"'{suggestion.get('name')}' in category '{suggestion.get('category')}') "
            "or adjust the rule's categories/tags/products."
        )
        return RulePreviewResponse(
            rule_id=rule_id,
            matched=matched,
            matched_products=[],
            feedback=feedback,
            needs_product=True,
            suggested_product=suggestion,
        )

    def review(self) -> RuleReviewResponse:
        rules = [json.loads(r.model_dump_json()) for r in self.rule_repo.list_rules()]
        review_text, source = self.llm_service.review_rules(rules)
        logger.info("ruleset reviewed via %s: %d rule(s)", source, len(rules))
        return RuleReviewResponse(review=review_text, source=source)
