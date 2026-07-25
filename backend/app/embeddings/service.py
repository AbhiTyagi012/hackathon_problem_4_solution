"""EmbeddingService: single seam for turning text into a vector.

Behind an ABC so the provider is swappable, mirroring app/llm/service.py's
discipline: the demo must never hard-depend on a live network/API key. When
Gemini is unavailable (no key, or the call fails), every embed() call falls
back to the same deterministic hashing-trick vector, so similarity ranking
still works end-to-end offline.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

FALLBACK_DIM = 256
BATCH_SIZE = 50  # Gemini's batchEmbedContents limit is 100; stay well under it


def fallback_embed(text: str) -> list[float]:
    """Deterministic hashing-trick vector: no model, no network, always available."""
    vec = [0.0] * FALLBACK_DIM
    for token in text.lower().split():
        idx = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % FALLBACK_DIM
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [v / norm for v in vec]


class EmbeddingService(ABC):
    @abstractmethod
    def is_enabled(self) -> bool: ...

    @abstractmethod
    def embed(self, text: str) -> tuple[list[float], str]: ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> tuple[list[list[float]], str]:
        """Embed many texts in as few network round-trips as possible — building
        an index one `embed()` call per item does N sequential requests, which
        for a catalog of a few hundred products means minutes of blocking
        startup latency. Real impls should batch; the ABC exists so building an
        index never has to choose between "slow" and "provider-specific"."""
        ...


class GeminiEmbeddingService(EmbeddingService):
    def __init__(self, settings: Settings):
        self._settings = settings

    def is_enabled(self) -> bool:
        return self._settings.embedding_enabled

    def embed(self, text: str) -> tuple[list[float], str]:
        if not self.is_enabled():
            logger.info("embed: Gemini disabled, using offline fallback vector")
            return fallback_embed(text), "fallback"
        try:
            resp = httpx.post(
                f"{self._settings.gemini_base_url}/models/{self._settings.gemini_embedding_model}:embedContent",
                params={"key": self._settings.gemini_api_key},
                json={"content": {"parts": [{"text": text}]}},
                timeout=self._settings.llm_timeout_seconds,
            )
            resp.raise_for_status()
            values = resp.json()["embedding"]["values"]
            logger.info("embed: Gemini embedded %d chars -> %d-dim vector", len(text), len(values))
            return values, "gemini"
        except Exception:
            logger.exception("Gemini embed failed, using offline fallback vector")
            return fallback_embed(text), "fallback"

    def embed_batch(self, texts: list[str]) -> tuple[list[list[float]], str]:
        if not texts:
            return [], "fallback"
        if not self.is_enabled():
            logger.info("embed_batch: Gemini disabled, using offline fallback vectors")
            return [fallback_embed(t) for t in texts], "fallback"
        try:
            model = self._settings.gemini_embedding_model
            all_values: list[list[float]] = []
            for start in range(0, len(texts), BATCH_SIZE):
                chunk = texts[start : start + BATCH_SIZE]
                resp = httpx.post(
                    f"{self._settings.gemini_base_url}/models/{model}:batchEmbedContents",
                    params={"key": self._settings.gemini_api_key},
                    json={
                        "requests": [
                            {"model": f"models/{model}", "content": {"parts": [{"text": t}]}} for t in chunk
                        ]
                    },
                    timeout=self._settings.llm_timeout_seconds,
                )
                resp.raise_for_status()
                all_values.extend(e["values"] for e in resp.json()["embeddings"])
            logger.info("embed_batch: Gemini embedded %d text(s) in %d batch call(s)", len(texts), -(-len(texts) // BATCH_SIZE))
            return all_values, "gemini"
        except Exception:
            logger.exception("Gemini embed_batch failed partway through; using offline fallback vectors for all")
            return [fallback_embed(t) for t in texts], "fallback"
