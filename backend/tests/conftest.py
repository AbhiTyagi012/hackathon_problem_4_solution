import shutil

import pytest

from app.catalog.repository import ProductRepository
from app.core.config import get_settings
from app.llm.service import GrokLLMService
from app.rules.repository import FileRuleRepository
from app.services.audit_store import InMemoryAuditStore
from app.services.recommendation_service import RecommendationService
from app.services.rule_admin_service import RuleAdminService


@pytest.fixture
def rule_repo(tmp_path):
    seeded_dir = get_settings().rules_dir
    shutil.copytree(seeded_dir, tmp_path, dirs_exist_ok=True)
    return FileRuleRepository(str(tmp_path))


@pytest.fixture
def product_repo():
    return ProductRepository(get_settings().catalog_path)


@pytest.fixture
def llm_service():
    settings = get_settings()
    settings.xai_api_key = ""  # force deterministic fallback path in tests
    return GrokLLMService(settings)


@pytest.fixture
def recommendation_service(rule_repo, product_repo):
    return RecommendationService(
        rule_repo=rule_repo,
        product_repo=product_repo,
        audit_store=InMemoryAuditStore(),
    )


@pytest.fixture
def rule_admin_service(rule_repo, product_repo, llm_service):
    return RuleAdminService(rule_repo=rule_repo, product_repo=product_repo, llm_service=llm_service)
