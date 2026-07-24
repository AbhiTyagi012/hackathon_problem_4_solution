"""Dependency wiring: singletons shared across requests, built once at startup."""
from __future__ import annotations

from functools import lru_cache

from app.catalog.repository import ProductRepository
from app.core.config import get_settings
from app.llm.service import GrokLLMService, LLMService
from app.rules.repository import FileRuleRepository, RuleRepository
from app.services.audit_store import AuditStore, InMemoryAuditStore
from app.services.recommendation_service import RecommendationService
from app.services.rule_admin_service import RuleAdminService


@lru_cache
def get_rule_repository() -> RuleRepository:
    return FileRuleRepository(get_settings().rules_dir)


@lru_cache
def get_product_repository() -> ProductRepository:
    return ProductRepository(get_settings().catalog_path)


@lru_cache
def get_audit_store() -> AuditStore:
    return InMemoryAuditStore()


@lru_cache
def get_llm_service() -> LLMService:
    return GrokLLMService(get_settings())


@lru_cache
def get_recommendation_service() -> RecommendationService:
    return RecommendationService(
        rule_repo=get_rule_repository(),
        product_repo=get_product_repository(),
        audit_store=get_audit_store(),
    )


@lru_cache
def get_rule_admin_service() -> RuleAdminService:
    return RuleAdminService(
        rule_repo=get_rule_repository(),
        product_repo=get_product_repository(),
        llm_service=get_llm_service(),
    )
