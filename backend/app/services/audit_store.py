"""In-memory audit history behind a swappable interface.

Kept as a simple list now; a DB-backed implementation could swap in later behind
the same three methods without touching any caller (evaluation/recommendation
services only ever call `record` / `get` / `list_recent`).
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from app.core.exceptions import DecisionNotFoundError
from app.models.schemas import Decision


class AuditStore(ABC):
    @abstractmethod
    def record(self, decision: Decision) -> Decision: ...

    @abstractmethod
    def get(self, decision_id: str) -> Decision: ...

    @abstractmethod
    def list_recent(self, limit: int = 50) -> list[Decision]: ...


class InMemoryAuditStore(AuditStore):
    def __init__(self):
        self._lock = threading.RLock()
        self._decisions: list[Decision] = []

    def record(self, decision: Decision) -> Decision:
        with self._lock:
            self._decisions.append(decision)
            return decision

    def get(self, decision_id: str) -> Decision:
        with self._lock:
            for d in reversed(self._decisions):
                if d.decision_id == decision_id:
                    return d
        raise DecisionNotFoundError(f"decision '{decision_id}' not found")

    def list_recent(self, limit: int = 50) -> list[Decision]:
        with self._lock:
            return list(reversed(self._decisions))[:limit]
