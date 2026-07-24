from app.core.config import get_settings
from app.embeddings.index import ProductVectorIndex
from app.embeddings.service import GeminiEmbeddingService, fallback_embed


def test_fallback_embed_is_deterministic():
    a = fallback_embed("gaming laptop")
    b = fallback_embed("gaming laptop")
    assert a == b


def test_fallback_embed_differs_for_different_text():
    assert fallback_embed("gaming laptop") != fallback_embed("beauty serum")


def test_fallback_embed_is_unit_normalized():
    vec = fallback_embed("gaming laptop accessory")
    norm = sum(v * v for v in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_embedding_service_disabled_without_api_key():
    settings = get_settings()
    settings.gemini_api_key = ""
    service = GeminiEmbeddingService(settings)
    assert not service.is_enabled()
    vec, source = service.embed("anything")
    assert source == "fallback"
    assert len(vec) > 0


def test_vector_index_search_excludes_requested_ids(product_repo, embedding_service):
    index = ProductVectorIndex(embedding_service, product_repo)
    query = index.get_vector("p001")
    results = index.search(query, k=5, exclude_ids={"p001"})
    assert "p001" not in {pid for pid, _ in results}
    assert len(results) <= 5


def test_vector_index_uses_fallback_source_without_api_key(product_repo, embedding_service):
    index = ProductVectorIndex(embedding_service, product_repo)
    index.get_vector("p001")  # forces the index to build
    assert index.source == "fallback"
