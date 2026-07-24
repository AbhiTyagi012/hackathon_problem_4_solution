"""LLMService: single seam for all Grok (xAI) calls.

Behind an ABC so the provider is swappable and so every feature has a deterministic
fallback path (app/llm/fallback.py) when no API key is configured or the call fails —
the demo must never hard-depend on a live network/API key.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.llm import fallback

logger = get_logger(__name__)


def _extract_json(text: str) -> dict | list:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


class LLMService(ABC):
    @abstractmethod
    def is_enabled(self) -> bool: ...

    @abstractmethod
    def nl_to_rule(self, text: str, operators: list[str], categories: list[str], tags: list[str]) -> tuple[dict, str]: ...

    @abstractmethod
    def review_rules(self, rules: list[dict]) -> tuple[str, str]: ...

    @abstractmethod
    def suggest_product_for_rule(self, rule: dict, categories: list[str], tags: list[str]) -> tuple[dict, str]: ...


class GrokLLMService(LLMService):
    def __init__(self, settings: Settings):
        self._settings = settings

    def is_enabled(self) -> bool:
        return self._settings.llm_enabled

    def _chat(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self._settings.grok_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.xai_api_key}"},
            json={
                "model": self._settings.grok_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=self._settings.llm_timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def nl_to_rule(self, text, operators, categories, tags):
        from app.llm.prompts import nl_to_rule_prompt

        if not self.is_enabled():
            logger.info("nl_to_rule: LLM disabled, using offline fallback parser")
            return fallback.nl_to_rule(text, categories, tags), "fallback"
        try:
            raw = self._chat(nl_to_rule_prompt(text, operators, categories, tags))
            logger.info("nl_to_rule: Grok generated a rule from %d chars of input text", len(text))
            return _extract_json(raw), "grok"
        except Exception:
            logger.exception("Grok nl_to_rule failed, using fallback")
            return fallback.nl_to_rule(text, categories, tags), "fallback"

    def review_rules(self, rules):
        from app.llm.prompts import review_rules_prompt

        if not self.is_enabled():
            logger.info("review_rules: LLM disabled, using offline heuristic review")
            return fallback.review_rules(rules), "fallback"
        try:
            review = self._chat(review_rules_prompt(json.dumps(rules)))
            logger.info("review_rules: Grok reviewed %d rule(s)", len(rules))
            return review, "grok"
        except Exception:
            logger.exception("Grok review_rules failed, using fallback")
            return fallback.review_rules(rules), "fallback"

    def suggest_product_for_rule(self, rule, categories, tags):
        from app.llm.prompts import suggest_product_prompt

        if not self.is_enabled():
            logger.info("suggest_product_for_rule: LLM disabled, using offline suggestion for rule '%s'", rule.get("id"))
            return fallback.suggest_product_for_rule(rule), "fallback"
        try:
            raw = self._chat(suggest_product_prompt(json.dumps(rule), categories, tags))
            logger.info("suggest_product_for_rule: Grok suggested a product for rule '%s'", rule.get("id"))
            return _extract_json(raw), "grok"
        except Exception:
            logger.exception("Grok suggest_product_for_rule failed, using fallback")
            return fallback.suggest_product_for_rule(rule), "fallback"
