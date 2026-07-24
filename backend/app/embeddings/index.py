"""FAISS-backed vector index over the product catalog.

Built lazily on first use from ProductRepository.list_products() — the catalog
is static JSON loaded once at startup, so a single lazily-built index (no
incremental updates) is sufficient. Each product is embedded once total;
embedding cost is independent of request volume.

If Gemini embeds some products but fails partway through (transient error),
the partial batch would have inconsistent dimensions against the deterministic
fallback vectors. Rather than risk a mixed vector space, any mismatch forces
the whole index to rebuild with fallback vectors uniformly.
"""
from __future__ import annotations

import faiss
import numpy as np

from app.catalog.repository import ProductRepository
from app.core.logging import get_logger
from app.embeddings.service import EmbeddingService, fallback_embed
from app.models.schemas import Product

logger = get_logger(__name__)


def product_text(product: Product) -> str:
    return f"{product.name} {product.category} {' '.join(product.tags)} {product.description}"


class ProductVectorIndex:
    def __init__(self, embedding_service: EmbeddingService, product_repo: ProductRepository):
        self._embedding_service = embedding_service
        self._product_repo = product_repo
        self._index: faiss.IndexFlatIP | None = None
        self._product_ids: list[str] = []
        self._vectors: dict[str, list[float]] = {}
        self.source = "fallback"

    def _ensure_built(self) -> None:
        if self._index is not None:
            return
        products = self._product_repo.list_products()
        vectors: list[list[float]] = []
        if self._embedding_service.is_enabled():
            try:
                vectors = [self._embedding_service.embed(product_text(p))[0] for p in products]
                if len({len(v) for v in vectors}) != 1:
                    raise ValueError("inconsistent embedding dimensions across catalog")
                self.source = "gemini"
            except Exception:
                logger.exception(
                    "embedding catalog failed partway through; rebuilding with offline fallback "
                    "vectors for the whole catalog to keep the vector space consistent"
                )
                vectors = []
        if not vectors:
            vectors = [fallback_embed(product_text(p)) for p in products]
            self.source = "fallback"

        matrix = np.array(vectors, dtype="float32")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        self._index = index
        self._product_ids = [p.id for p in products]
        self._vectors = {p.id: vec for p, vec in zip(products, vectors)}
        logger.info("built FAISS index over %d product(s), dim=%d, source=%s", len(products), matrix.shape[1], self.source)

    def get_vector(self, product_id: str) -> list[float] | None:
        """Already-computed vector for a catalog product — avoids re-embedding."""
        self._ensure_built()
        return self._vectors.get(product_id)

    def embed_query(self, text: str) -> list[float]:
        """For arbitrary text not already in the catalog (e.g. a free-text query)."""
        self._ensure_built()  # guarantees fallback/real decision already made for this vector space
        vec, _source = self._embedding_service.embed(text)
        return vec

    def search(self, query_vector: list[float], k: int, exclude_ids: set[str] | None = None) -> list[tuple[str, float]]:
        self._ensure_built()
        exclude_ids = exclude_ids or set()
        query = np.array([query_vector], dtype="float32")
        faiss.normalize_L2(query)
        fetch_k = min(len(self._product_ids), k + len(exclude_ids) + 5) or 1
        scores, indices = self._index.search(query, fetch_k)
        results: list[tuple[str, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            product_id = self._product_ids[idx]
            if product_id in exclude_ids:
                continue
            results.append((product_id, float(score)))
            if len(results) >= k:
                break
        return results
