"""Admin-facing rule management: CRUD, reorder, NL authoring, preview, and the
post-save catalog-match feedback loop backed by Groq."""
from __future__ import annotations

import json
import re
import uuid

from app.catalog.repository import ProductRepository
from app.core.exceptions import RuleConflictError, RuleValidationError
from app.core.logging import get_logger
from app.embeddings.rule_index import RuleVectorIndex
from app.engine.condition_evaluator import evaluate_condition
from app.engine.operators import available_operators
from app.llm.service import LLMService
from app.models.schemas import (
    Condition,
    ConflictCheckResult,
    NlRuleResponse,
    PipelineStep,
    Profile,
    Rule,
    RuleConflictCandidate,
    RuleCreate,
    RuleDraftPipelineResponse,
    RulePreviewResponse,
    RuleReviewResponse,
)
from app.rules.repository import RuleRepository
from app.services.recommendation_service import resolve_recommend_targets

logger = get_logger(__name__)

_RAG_CANDIDATES_K = 3


def _draft_query_text(data: dict) -> str:
    cond = data.get("condition") or {}
    recommend = data.get("recommend") or {}
    return (
        f"{data.get('name', '')} {data.get('description', '')} "
        f"{cond.get('field', '')} {cond.get('value', '')} "
        f"{' '.join(recommend.get('categories') or [])} {' '.join(recommend.get('tags') or [])}"
    )

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
    def __init__(
        self,
        rule_repo: RuleRepository,
        product_repo: ProductRepository,
        llm_service: LLMService,
        rule_vector_index: RuleVectorIndex,
    ):
        self.rule_repo = rule_repo
        self.product_repo = product_repo
        self.llm_service = llm_service
        self.rule_vector_index = rule_vector_index

    # -- CRUD --------------------------------------------------------------- #
    def list_rules(self) -> list[Rule]:
        return self.rule_repo.list_rules()

    def get_rule(self, rule_id: str) -> Rule:
        return self.rule_repo.get(rule_id)

    def create_rule(self, payload: RuleCreate) -> Rule:
        data = payload.model_dump(exclude={"confirm_conflict"})
        if not payload.confirm_conflict:
            self._block_if_conflicting(data)
        rule = Rule(id=_slugify(payload.name), **data)
        created = self.rule_repo.add(rule)
        self.rule_vector_index.invalidate()
        logger.info("rule created: id=%s name=%r priority=%d", created.id, created.name, created.priority)
        return created

    def update_rule(self, rule_id: str, payload: RuleCreate) -> Rule:
        existing = self.rule_repo.get(rule_id)
        data = payload.model_dump(exclude={"confirm_conflict"})
        if not payload.confirm_conflict:
            self._block_if_conflicting(data, exclude_rule_id=rule_id)
        merged = {**existing.model_dump(), **data}
        updated = Rule.model_validate(merged)
        saved = self.rule_repo.update(updated)
        self.rule_vector_index.invalidate()
        logger.info("rule updated: id=%s name=%r version=%d", saved.id, saved.name, saved.version)
        return saved

    def _block_if_conflicting(self, data: dict, exclude_rule_id: str | None = None) -> None:
        """Enforces the RAG conflict-check at the actual save path (not just the
        optional NL-preview pipeline), so it applies regardless of how the rule
        was authored — manual entry, edit, or NL generation. Raises
        RuleConflictError (409) carrying the ConflictCheckResult; the caller
        (frontend) shows the specific conflicting rule(s) and can retry with
        `confirm_conflict=true` once the admin explicitly confirms."""
        conflict_check, _ = self._retrieve_and_check_conflicts(data, exclude_rule_id=exclude_rule_id)
        if conflict_check.verdict != "ok":
            logger.info(
                "rule save blocked pending confirmation: verdict=%s candidates=%s",
                conflict_check.verdict,
                [c.rule_id for c in conflict_check.candidates],
            )
            raise RuleConflictError(
                f"This rule may {conflict_check.verdict} with an existing rule — confirm to save anyway.",
                detail=conflict_check.model_dump(),
            )

    def delete_rule(self, rule_id: str) -> None:
        self.rule_repo.delete(rule_id)
        self.rule_vector_index.invalidate()
        logger.info("rule deleted: id=%s", rule_id)

    def reorder(self, ordered_ids: list[str]) -> list[Rule]:
        reordered = self.rule_repo.reorder(ordered_ids)
        logger.info("rules reordered: %s", ordered_ids)
        return reordered

    # -- Groq-backed features ------------------------------------------------ #
    def nl_to_rule(self, text: str) -> NlRuleResponse:
        categories = self.product_repo.categories()
        tags = self.product_repo.tags()
        data, source = self.llm_service.nl_to_rule(text, available_operators(), categories, tags)
        if data is None:
            logger.info("nl_to_rule: %s could not confidently parse text %r", source, text)
            return NlRuleResponse(
                rule=None,
                source=source,
                notes=(
                    "This type of rule isn't supported yet. Try describing it in terms of a "
                    "shopper's purchase history (e.g. gaming, beauty, travel) or budget."
                ),
            )
        try:
            rule_create = RuleCreate.model_validate(data)
        except Exception as exc:
            logger.error("nl_to_rule produced an invalid rule from text %r: %s", text, exc)
            raise RuleValidationError(f"AI produced an invalid rule: {exc}") from exc
        logger.info("rule drafted from text via %s: %r", source, rule_create.name)
        return NlRuleResponse(rule=rule_create, source=source, notes=f"Generated via {source}")

    def _retrieve_and_check_conflicts(
        self, data: dict, exclude_rule_id: str | None = None
    ) -> tuple[ConflictCheckResult, list[PipelineStep]]:
        """RAG: retrieve the top-k existing rules similar to `data`, then ask the
        LLM (or offline heuristic) whether it actually conflicts with any of
        them. Shared by draft_rule_with_pipeline (preview, non-blocking) and
        _block_if_conflicting (the actual save-path enforcement)."""
        steps: list[PipelineStep] = []
        query_vec = self.rule_vector_index.embed_query(_draft_query_text(data))
        retrieved = self.rule_vector_index.search(query_vec, k=_RAG_CANDIDATES_K, exclude_rule_id=exclude_rule_id)
        retrieved_rules: dict[str, tuple[float, Rule]] = {}
        for rule_id, score in retrieved:
            try:
                retrieved_rules[rule_id] = (score, self.rule_repo.get(rule_id))
            except Exception:
                continue
        steps.append(
            PipelineStep(
                agent="Retriever", status="ok", detail=f"found {len(retrieved_rules)} similar existing rule(s)"
            )
        )

        if not retrieved_rules:
            conflict_check = ConflictCheckResult(
                verdict="ok", candidates=[], notes="No similar existing rules to compare against.", source="none"
            )
            steps.append(PipelineStep(agent="Conflict-checker", status="ok", detail="skipped — nothing retrieved"))
            return conflict_check, steps

        candidate_dicts = [json.loads(rule.model_dump_json()) for _, rule in retrieved_rules.values()]
        conflict_data, conflict_source = self.llm_service.check_rule_conflicts(data, candidate_dicts)
        flagged: list[RuleConflictCandidate] = []
        for item in (conflict_data or {}).get("candidates", []):
            rid = item.get("rule_id")
            if rid in retrieved_rules:
                score, rule_obj = retrieved_rules[rid]
                flagged.append(
                    RuleConflictCandidate(
                        rule_id=rid, rule_name=rule_obj.name, similarity=score, note=item.get("note", "")
                    )
                )
        conflict_check = ConflictCheckResult(
            verdict=(conflict_data or {}).get("verdict", "ok"),
            candidates=flagged,
            notes=(conflict_data or {}).get("notes", ""),
            source=conflict_source,
        )
        steps.append(
            PipelineStep(
                agent="Conflict-checker", status="ok", detail=f"verdict={conflict_check.verdict} via {conflict_source}"
            )
        )
        return conflict_check, steps

    def draft_rule_with_pipeline(self, text: str) -> RuleDraftPipelineResponse:
        """Interpret -> Retrieve (RAG) -> Conflict-check -> Validate/repair -> Preview.

        Each step is recorded as a PipelineStep so the admin can see what
        happened, rather than a single opaque LLM call. This is a preview only
        — it doesn't save anything, so its ConflictCheckResult is informational.
        The actual enforcement (block unless confirmed) happens in
        create_rule/update_rule via _block_if_conflicting, which re-runs the
        same check at save time in case the admin edited the draft in between.
        """
        steps: list[PipelineStep] = []
        categories = self.product_repo.categories()
        tags = self.product_repo.tags()

        # 1. Interpreter
        data, source = self.llm_service.nl_to_rule(text, available_operators(), categories, tags)
        if data is None:
            notes = (
                "This type of rule isn't supported yet. Try describing it in terms of a "
                "shopper's purchase history (e.g. gaming, beauty, travel) or budget."
            )
            steps.append(PipelineStep(agent="Interpreter", status="unsupported", detail=notes))
            logger.info("draft_rule_with_pipeline: %s could not confidently parse text %r", source, text)
            return RuleDraftPipelineResponse(rule=None, steps=steps, source=source, notes=notes)
        steps.append(PipelineStep(agent="Interpreter", status="ok", detail=f"drafted via {source}"))

        # 2-3. Retriever (RAG) + Conflict-checker
        conflict_check, conflict_steps = self._retrieve_and_check_conflicts(data)
        steps.extend(conflict_steps)

        # 4. Validator — one repair attempt via the LLM on failure; offline fallback can't repair.
        try:
            rule_create = RuleCreate.model_validate(data)
            steps.append(PipelineStep(agent="Validator", status="ok"))
        except Exception as exc:
            repaired_data, repair_source = self.llm_service.repair_rule(data, str(exc), available_operators())
            try:
                if repaired_data is None:
                    raise ValueError("no repair available")
                rule_create = RuleCreate.model_validate(repaired_data)
                steps.append(
                    PipelineStep(agent="Validator", status="repaired", detail=f"fixed via {repair_source}: {exc}")
                )
                data = repaired_data
            except Exception:
                steps.append(PipelineStep(agent="Validator", status="failed", detail=str(exc)))
                logger.error("draft_rule_with_pipeline: repair failed for text %r: %s", text, exc)
                return RuleDraftPipelineResponse(
                    rule=None,
                    conflict_check=conflict_check,
                    steps=steps,
                    source=source,
                    notes=f"AI produced an invalid rule and repair failed: {exc}",
                )

        # 5. Previewer — reuses the same evaluation path as preview()/preview_draft().
        preview = self._preview("draft", rule_create.condition, rule_create.recommend, None, data)
        steps.append(PipelineStep(agent="Previewer", status="ok", detail=preview.feedback))

        logger.info("draft_rule_with_pipeline: completed for text %r via %s", text, source)
        return RuleDraftPipelineResponse(
            rule=rule_create,
            conflict_check=conflict_check,
            preview=preview,
            steps=steps,
            source=source,
            notes=f"Generated via {source}",
        )

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
