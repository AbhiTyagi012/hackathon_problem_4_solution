import json
import shutil

import pytest

from app.catalog.repository import ProductRepository
from app.core.config import get_settings
from app.embeddings.index import ProductVectorIndex
from app.embeddings.rule_index import RuleVectorIndex
from app.embeddings.service import GeminiEmbeddingService
from app.history.repository import FilePurchaseHistoryRepository
from app.llm.service import GroqLLMService
from app.rules.repository import FileRuleRepository
from app.services.audit_store import InMemoryAuditStore
from app.services.recommendation_service import RecommendationService
from app.services.rule_admin_service import RuleAdminService

# Known seeded shoppers used across tests — chosen so their purchased products'
# tags line up with real rules in the seeded ruleset (rule-fitness, rule-beauty).
SHOPPER_FITNESS = "shopper-fitness"  # purchased p013: tags sports, running, fitness, footwear
SHOPPER_BEAUTY = "shopper-beauty"  # purchased p017: tags beauty, skincare, wellness
SHOPPER_COLD = "shopper-cold-xyz"  # no purchase history at all


@pytest.fixture
def rule_repo(tmp_path):
    seeded_dir = get_settings().rules_dir
    shutil.copytree(seeded_dir, tmp_path, dirs_exist_ok=True)
    return FileRuleRepository(str(tmp_path))


@pytest.fixture
def product_repo():
    return ProductRepository(get_settings().catalog_path)


@pytest.fixture
def purchase_history_repo(tmp_path):
    history_path = tmp_path / "purchase_history.json"
    history_path.write_text(
        json.dumps(
            {
                SHOPPER_FITNESS: {"purchased_product_ids": ["p013"]},
                SHOPPER_BEAUTY: {"purchased_product_ids": ["p017"]},
            }
        ),
        encoding="utf-8",
    )
    return FilePurchaseHistoryRepository(str(history_path))


@pytest.fixture
def llm_service():
    settings = get_settings()
    settings.groq_api_key = ""  # force deterministic fallback path in tests
    return GroqLLMService(settings)


@pytest.fixture
def embedding_service():
    settings = get_settings()
    settings.gemini_api_key = ""  # force deterministic fallback path in tests
    return GeminiEmbeddingService(settings)


@pytest.fixture
def vector_index(embedding_service, product_repo):
    # storage_dir=None: in-memory only, keeps tests isolated/fast. Persistence
    # has its own dedicated test that constructs a ProductVectorIndex directly
    # with a tmp_path storage dir.
    return ProductVectorIndex(embedding_service, product_repo, storage_dir=None)


@pytest.fixture
def rule_vector_index(embedding_service, rule_repo):
    return RuleVectorIndex(embedding_service, rule_repo)


@pytest.fixture
def recommendation_service(rule_repo, product_repo, purchase_history_repo, vector_index):
    return RecommendationService(
        rule_repo=rule_repo,
        product_repo=product_repo,
        audit_store=InMemoryAuditStore(),
        purchase_history_repo=purchase_history_repo,
        vector_index=vector_index,
    )


@pytest.fixture
def rule_admin_service(rule_repo, product_repo, llm_service, rule_vector_index):
    return RuleAdminService(
        rule_repo=rule_repo, product_repo=product_repo, llm_service=llm_service, rule_vector_index=rule_vector_index
    )
