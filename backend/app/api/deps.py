"""Dependency wiring: singletons shared across requests, built once at startup."""
from __future__ import annotations

from functools import lru_cache

from app.catalog.repository import ProductRepository
from app.core.config import get_settings
from app.embeddings.index import ProductVectorIndex
from app.embeddings.service import EmbeddingService, GeminiEmbeddingService
from app.history.repository import FilePurchaseHistoryRepository, PurchaseHistoryRepository
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
def get_purchase_history_repository() -> PurchaseHistoryRepository:
    return FilePurchaseHistoryRepository(get_settings().purchase_history_path)


@lru_cache
def get_audit_store() -> AuditStore:
    return InMemoryAuditStore()


@lru_cache
def get_llm_service() -> LLMService:
    return GrokLLMService(get_settings())


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return GeminiEmbeddingService(get_settings())


@lru_cache
def get_vector_index() -> ProductVectorIndex:
    return ProductVectorIndex(get_embedding_service(), get_product_repository())


@lru_cache
def get_recommendation_service() -> RecommendationService:
    return RecommendationService(
        rule_repo=get_rule_repository(),
        product_repo=get_product_repository(),
        audit_store=get_audit_store(),
        purchase_history_repo=get_purchase_history_repository(),
        vector_index=get_vector_index(),
    )


@lru_cache
def get_rule_admin_service() -> RuleAdminService:
    return RuleAdminService(
        rule_repo=get_rule_repository(),
        product_repo=get_product_repository(),
        llm_service=get_llm_service(),
    )
