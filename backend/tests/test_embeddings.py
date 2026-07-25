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


def test_embed_batch_matches_individual_embeds_offline(embedding_service):
    texts = ["gaming laptop", "beauty serum", "travel backpack"]
    batch_vectors, source = embedding_service.embed_batch(texts)
    assert source == "fallback"
    assert batch_vectors == [fallback_embed(t) for t in texts]


def test_embed_batch_empty_list(embedding_service):
    assert embedding_service.embed_batch([]) == ([], "fallback")


def test_vector_index_persists_and_reloads_without_rebuilding(tmp_path, embedding_service, product_repo):
    storage_dir = str(tmp_path / "embeddings")
    built = ProductVectorIndex(embedding_service, product_repo, storage_dir)
    built.get_vector("p001")  # forces build + save()

    assert (tmp_path / "embeddings" / "product_index.faiss").exists()
    assert (tmp_path / "embeddings" / "product_index.json").exists()

    reloaded = ProductVectorIndex(embedding_service, product_repo, storage_dir)
    reloaded_vec = reloaded.get_vector("p001")
    assert reloaded_vec == built.get_vector("p001")
    assert reloaded.source == built.source


def test_vector_index_rebuilds_when_catalog_ids_change(tmp_path, embedding_service, product_repo):
    storage_dir = str(tmp_path / "embeddings")
    built = ProductVectorIndex(embedding_service, product_repo, storage_dir)
    built.get_vector("p001")

    # Simulate a changed catalog by tampering with the persisted sidecar's id list —
    # the loader should detect the mismatch and refuse to load stale data.
    import json

    sidecar_path = tmp_path / "embeddings" / "product_index.json"
    sidecar = json.loads(sidecar_path.read_text())
    sidecar["product_ids"] = ["not-a-real-product"]
    sidecar_path.write_text(json.dumps(sidecar))

    rebuilt = ProductVectorIndex(embedding_service, product_repo, storage_dir)
    rebuilt.get_vector("p001")
    assert rebuilt._product_ids == built._product_ids  # rebuilt from the real catalog, not the stale sidecar
