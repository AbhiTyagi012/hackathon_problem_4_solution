"""FAISS-backed vector index over the ruleset — the retrieval step (RAG) for
rule-authoring conflict-checking.

Deliberately not persisted to disk, unlike ProductVectorIndex: the ruleset is
small (~10 rules) and mutates on every create/update/delete, whereas the
catalog is larger and static. Rebuilding a small flat index from the YAML
(already the source of truth) on invalidation is cheap; keeping a persisted
rule-index in sync with the file across restarts would be complexity with no
real benefit here.
"""
from __future__ import annotations

import faiss
import numpy as np

from app.core.logging import get_logger
from app.embeddings.service import EmbeddingService
from app.models.schemas import Rule
from app.rules.repository import RuleRepository

logger = get_logger(__name__)


def rule_text(rule: Rule) -> str:
    return (
        f"{rule.name} {rule.description} {rule.condition.summarize()} "
        f"{' '.join(rule.recommend.categories)} {' '.join(rule.recommend.tags)}"
    )


class RuleVectorIndex:
    def __init__(self, embedding_service: EmbeddingService, rule_repo: RuleRepository):
        self._embedding_service = embedding_service
        self._rule_repo = rule_repo
        self._index: faiss.IndexFlatIP | None = None
        self._rule_ids: list[str] = []
        self.source = "fallback"

    def invalidate(self) -> None:
        """Called after create/update/delete so the next search rebuilds from
        the current ruleset — reorder doesn't change rule content, so it
        doesn't need to invalidate."""
        self._index = None

    def _ensure_built(self) -> None:
        if self._index is not None:
            return
        rules = self._rule_repo.list_rules()
        if not rules:
            self._rule_ids = []
            return
        vectors, self.source = self._embedding_service.embed_batch([rule_text(r) for r in rules])

        matrix = np.array(vectors, dtype="float32")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        self._index = index
        self._rule_ids = [r.id for r in rules]
        logger.info("built rule vector index over %d rule(s), source=%s", len(rules), self.source)

    def embed_query(self, text: str) -> list[float]:
        self._ensure_built()
        vec, _source = self._embedding_service.embed(text)
        return vec

    def search(self, query_vector: list[float], k: int, exclude_rule_id: str | None = None) -> list[tuple[str, float]]:
        self._ensure_built()
        if not self._rule_ids:
            return []
        query = np.array([query_vector], dtype="float32")
        faiss.normalize_L2(query)
        exclude = {exclude_rule_id} if exclude_rule_id else set()
        fetch_k = min(len(self._rule_ids), k + len(exclude) + 2) or 1
        scores, indices = self._index.search(query, fetch_k)
        results: list[tuple[str, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            rule_id = self._rule_ids[idx]
            if rule_id in exclude:
                continue
            results.append((rule_id, float(score)))
            if len(results) >= k:
                break
        return results
