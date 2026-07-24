"""Purchase history storage behind an interface, mirroring RuleRepository.

Interest is no longer self-reported (see Profile) — it's derived from what a
shopper has actually bought. This repo is the source of truth for that: given
a shopper id, which products have they purchased. A DB-backed implementation
could swap in later without touching any caller.
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class PurchaseHistoryRepository(ABC):
    @abstractmethod
    def get(self, shopper_id: str) -> list[str]: ...

    @abstractmethod
    def record_purchase(self, shopper_id: str, product_id: str) -> None: ...


class FilePurchaseHistoryRepository(PurchaseHistoryRepository):
    def __init__(self, history_path: str):
        self._path = Path(history_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._history: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._history = {}
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._history = {
            shopper_id: list(entry.get("purchased_product_ids", []))
            for shopper_id, entry in data.items()
        }
        logger.info("loaded purchase history for %d shopper(s) from %s", len(self._history), self._path)

    def _persist(self) -> None:
        payload = {
            shopper_id: {"purchased_product_ids": product_ids}
            for shopper_id, product_ids in self._history.items()
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, shopper_id: str) -> list[str]:
        with self._lock:
            return list(self._history.get(shopper_id, []))

    def record_purchase(self, shopper_id: str, product_id: str) -> None:
        with self._lock:
            products = self._history.setdefault(shopper_id, [])
            products.append(product_id)
            self._persist()
            logger.info("recorded purchase: shopper=%s product=%s", shopper_id, product_id)
