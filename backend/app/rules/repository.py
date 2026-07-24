"""Rule storage behind an interface so a DB-backed repo can swap in later.

FileRuleRepository loads every *.yaml / *.json file in the rules directory and
persists changes back to a single canonical file. All access is by rule id.
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path

import yaml

from app.core.exceptions import RuleNotFoundError, RuleValidationError
from app.core.logging import get_logger
from app.models.schemas import Rule, utcnow

logger = get_logger(__name__)


class RuleRepository(ABC):
    @abstractmethod
    def list_rules(self) -> list[Rule]: ...

    @abstractmethod
    def get(self, rule_id: str) -> Rule: ...

    @abstractmethod
    def add(self, rule: Rule) -> Rule: ...

    @abstractmethod
    def update(self, rule: Rule) -> Rule: ...

    @abstractmethod
    def delete(self, rule_id: str) -> None: ...

    @abstractmethod
    def reorder(self, ordered_ids: list[str]) -> list[Rule]: ...


class FileRuleRepository(RuleRepository):
    def __init__(self, rules_dir: str):
        self.rules_dir = Path(rules_dir)
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self._store_path = self.rules_dir / "ecommerce_rules.yaml"
        self._lock = threading.RLock()
        self._rules: dict[str, Rule] = {}
        self._load()

    # -- loading / persistence --------------------------------------------- #
    def _load(self) -> None:
        self._rules = {}
        for path in sorted(self.rules_dir.iterdir()):
            if path.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
            for item in (data or {}).get("rules", []):
                rule = Rule.model_validate(item)
                self._rules[rule.id] = rule
        logger.info("loaded %d rules from %s", len(self._rules), self.rules_dir)

    def _persist(self) -> None:
        payload = {
            "rules": [
                json.loads(r.model_dump_json())
                for r in sorted(self._rules.values(), key=lambda r: r.priority, reverse=True)
            ]
        }
        self._store_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    # -- interface --------------------------------------------------------- #
    def list_rules(self) -> list[Rule]:
        with self._lock:
            return sorted(self._rules.values(), key=lambda r: r.priority, reverse=True)

    def get(self, rule_id: str) -> Rule:
        with self._lock:
            if rule_id not in self._rules:
                raise RuleNotFoundError(f"rule '{rule_id}' not found")
            return self._rules[rule_id]

    def add(self, rule: Rule) -> Rule:
        with self._lock:
            self._rules[rule.id] = rule
            self._persist()
            return rule

    def update(self, rule: Rule) -> Rule:
        with self._lock:
            if rule.id not in self._rules:
                raise RuleNotFoundError(f"rule '{rule.id}' not found")
            rule.version = self._rules[rule.id].version + 1
            rule.updated_at = utcnow()
            self._rules[rule.id] = rule
            self._persist()
            return rule

    def delete(self, rule_id: str) -> None:
        with self._lock:
            if rule_id not in self._rules:
                raise RuleNotFoundError(f"rule '{rule_id}' not found")
            del self._rules[rule_id]
            self._persist()

    def reorder(self, ordered_ids: list[str]) -> list[Rule]:
        """Assign descending priorities following the given id order.

        ``ordered_ids`` must be a permutation of every existing rule id — reordering
        is a full-table operation (matches a drag-to-reorder admin UI), so a partial
        list would leave stale priorities among the untouched rules.
        """
        with self._lock:
            missing = [rid for rid in ordered_ids if rid not in self._rules]
            if missing:
                raise RuleNotFoundError(f"unknown rule ids: {missing}")
            if set(ordered_ids) != set(self._rules.keys()):
                raise RuleValidationError(
                    "reorder requires every existing rule id exactly once"
                )
            step = 10
            top = step * len(ordered_ids)
            for offset, rid in enumerate(ordered_ids):
                self._rules[rid].priority = top - offset * step
                self._rules[rid].updated_at = utcnow()
            self._persist()
            return self.list_rules()
