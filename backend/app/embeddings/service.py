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
