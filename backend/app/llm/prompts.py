"""Prompt builders for the Groq-backed LLM features."""
from __future__ import annotations

import json

CONTEXT_FIELDS = [
    "purchase_tags (list of strings, e.g. gaming, music, fitness, beauty, travel — derived "
    "server-side from what the shopper has actually bought, not self-reported)",
    "budget_band (string: low|medium|high)",
    "max_budget (number)",
]


def nl_to_rule_prompt(text: str, operators: list[str], categories: list[str], tags: list[str]) -> str:
    schema = {
        "name": "short human name",
        "description": "one sentence",
        "priority": 80,
        "condition": {
            "all | any": [
                {"field": "<one of the context fields>", "operator": "<one operator>", "value": "<value>"}
            ]
        },
        "recommend": {
            "products": ["optional product ids"],
            "categories": ["optional category names"],
            "tags": ["optional tag names"],
            "score": 1.0,
        },
    }
    unsupported_schema = {"unsupported": True, "reason": "one short sentence"}
    return (
        "You convert a plain-English e-commerce recommendation rule into strict JSON.\n"
        f"Available context fields (this is the FULL supported scope for now — nothing else): "
        f"{', '.join(CONTEXT_FIELDS)}.\n"
        f"Available operators: {', '.join(operators)}.\n"
        f"Available product categories: {', '.join(categories)}.\n"
        f"Available product tags: {', '.join(tags)}.\n\n"
        "A condition is either a leaf {field, operator, value} or a group "
        "{all:[...]} / {any:[...]} / {not:{...}}.\n"
        "The 'recommend' block must reference real categories/tags (or product ids) so it "
        "actually matches catalog products. Prefer tags/categories over specific product ids.\n\n"
        "If the request needs a signal that is NOT one of the available context fields above "
        "(e.g. age, gender, location, or anything else outside that list) — do not substitute an "
        f"unrelated field or guess. Instead return ONLY: {json.dumps(unsupported_schema)}\n\n"
        f"Otherwise return ONLY a JSON object shaped like:\n{json.dumps(schema, indent=2)}\n\n"
        f"Rule description: \"{text}\"\n"
        "JSON:"
    )


def check_rule_conflicts_prompt(draft_json: str, candidates_json: str) -> str:
    return (
        "You are checking whether a NEW draft recommendation rule conflicts with a small set of "
        "EXISTING rules that were retrieved because they are similar to it (not the whole ruleset "
        "— just these retrieved candidates).\n"
        f"Draft rule: {draft_json}\n"
        f"Retrieved similar existing rules: {candidates_json}\n\n"
        "Decide: does the draft exactly duplicate one of these (same condition AND same recommend "
        "targets), overlap with one (same condition field with an overlapping value, but different "
        "recommend targets or priority), or is it genuinely distinct (\"ok\")?\n"
        'Return ONLY JSON: {"verdict": "ok" | "overlap" | "duplicate", '
        '"candidates": [{"rule_id": "...", "note": "one short sentence"}], "notes": "one short '
        'sentence"}. Only include a candidate in "candidates" if it actually conflicts — omit ones '
        "that are merely topically similar but don't actually overlap."
    )


def repair_rule_prompt(draft_json: str, error: str, operators: list[str]) -> str:
    return (
        "The following draft recommendation rule JSON failed schema validation.\n"
        f"Draft: {draft_json}\n"
        f"Validation error: {error}\n"
        f"Available operators: {', '.join(operators)}\n\n"
        "Fix ONLY what's necessary to make it valid — keep the rest unchanged (same intent, same "
        "recommend targets where possible). Return ONLY the corrected JSON object, same shape as "
        "the draft."
    )


def review_rules_prompt(rules_json: str) -> str:
    return (
        "You are reviewing a set of e-commerce recommendation rules for quality.\n"
        f"Rules: {rules_json}\n\n"
        "Point out (a) conflicts or overlaps, (b) redundant rules, (c) gaps where common "
        "shoppers would get no recommendation. Be concise and use short bullet points."
    )


def suggest_product_prompt(rule_json: str, categories: list[str], tags: list[str]) -> str:
    return (
        "A new recommendation rule matches NO product in the catalog. Suggest ONE product to add "
        "so the rule becomes useful.\n"
        f"Rule: {rule_json}\n"
        f"Existing categories: {', '.join(categories)}\n"
        f"Existing tags: {', '.join(tags)}\n\n"
        'Return ONLY JSON: {"name": "...", "category": "...", "price": 0, "brand": "...", '
        '"tags": ["..."], "description": "..."}.'
    )
