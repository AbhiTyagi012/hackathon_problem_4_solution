"""FAISS-backed vector index over the product catalog.

Built lazily on first use from ProductRepository.list_products() — the catalog
is static JSON loaded once at startup, so a single lazily-built index (no
incremental updates) is sufficient. Each product is embedded once total;
embedding cost is independent of request volume.

Persisted to disk (`save`/`_try_load`) so a process restart doesn't re-embed
the whole catalog — the sidecar's product-id list is the invalidation check:
if the catalog changed since the index was saved, the ids won't match and the
index rebuilds (and re-saves) from scratch.

If Gemini embeds some products but fails partway through (transient error),
the partial batch would have inconsistent dimensions against the deterministic
fallback vectors. Rather than risk a mixed vector space, any mismatch forces
the whole index to rebuild with fallback vectors uniformly.
"""
from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from app.catalog.repository import ProductRepository
from app.core.logging import get_logger
from app.embeddings.service import EmbeddingService
from app.models.schemas import Product

logger = get_logger(__name__)


def product_text(product: Product) -> str:
    return f"{product.name} {product.category} {' '.join(product.tags)} {product.description}"


class ProductVectorIndex:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        product_repo: ProductRepository,
        storage_dir: str | None = None,
    ):
        self._embedding_service = embedding_service
        self._product_repo = product_repo
        self._storage_dir = Path(storage_dir) if storage_dir else None
        self._index: faiss.IndexFlatIP | None = None
        self._product_ids: list[str] = []
        self._vectors: dict[str, list[float]] = {}
        self.source = "fallback"

    @property
    def _index_path(self) -> Path | None:
        return self._storage_dir / "product_index.faiss" if self._storage_dir else None

    @property
    def _sidecar_path(self) -> Path | None:
        return self._storage_dir / "product_index.json" if self._storage_dir else None

    def _try_load(self, current_ids: list[str]) -> bool:
        if not self._index_path or not self._index_path.exists() or not self._sidecar_path.exists():
            return False
        sidecar = json.loads(self._sidecar_path.read_text(encoding="utf-8"))
        if sidecar.get("product_ids") != current_ids:
            logger.info("persisted product index is stale (catalog changed) — rebuilding")
            return False
        index = faiss.read_index(str(self._index_path))
        self._index = index
        self._product_ids = sidecar["product_ids"]
        self.source = sidecar["source"]
        self._vectors = {
            pid: index.reconstruct(i).tolist() for i, pid in enumerate(self._product_ids)
        }
        logger.info(
            "loaded persisted FAISS index over %d product(s) from %s (source=%s)",
            len(self._product_ids), self._index_path, self.source,
        )
        return True

    def save(self) -> None:
        if not self._index_path or self._index is None:
            return
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._index_path))
        self._sidecar_path.write_text(
            json.dumps({"product_ids": self._product_ids, "source": self.source}), encoding="utf-8"
        )
        logger.info("persisted FAISS index to %s", self._index_path)

    def _ensure_built(self) -> None:
        if self._index is not None:
            return
        products = self._product_repo.list_products()
        current_ids = [p.id for p in products]
        if self._try_load(current_ids):
            return

        # embed_batch does a handful of batched network calls instead of one per product (a
        # few hundred sequential calls would take minutes) and is itself atomic: any failure
        # partway through falls back to fallback vectors for the whole catalog, so there's no
        # risk of a mixed-dimension vector space here.
        vectors, self.source = self._embedding_service.embed_batch([product_text(p) for p in products])

        matrix = np.array(vectors, dtype="float32")
        faiss.normalize_L2(matrix)  # in-place; `matrix` (not `vectors`) is now unit-normalized
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        self._index = index
        self._product_ids = current_ids
        # Store the normalized vectors (matching what `index.reconstruct()` returns after a
        # persisted reload) so `get_vector()` behaves identically whether freshly built or loaded.
        self._vectors = {pid: matrix[i].tolist() for i, pid in enumerate(current_ids)}
        logger.info("built FAISS index over %d product(s), dim=%d, source=%s", len(products), matrix.shape[1], self.source)
        self.save()

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
