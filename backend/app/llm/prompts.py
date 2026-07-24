"""Prompt builders for the Grok-backed LLM features."""
from __future__ import annotations

import json

CONTEXT_FIELDS = [
    "age (int)",
    "gender (string)",
    "interests (list of strings, e.g. gaming, music, fitness, beauty, travel)",
    "budget_band (string: low|medium|high)",
    "max_budget (number)",
    "location (string)",
    "past_purchase_categories (list of strings)",
    "context_type (string: home|search|purchase)",
    "search_query (string)",
    "search_category (string)",
    "purchased_category (string)",
    "purchased_tags (list of strings)",
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
            "score": 2.0,
        },
    }
    return (
        "You convert a plain-English e-commerce recommendation rule into strict JSON.\n"
        f"Available context fields: {', '.join(CONTEXT_FIELDS)}.\n"
        f"Available operators: {', '.join(operators)}.\n"
        f"Available product categories: {', '.join(categories)}.\n"
        f"Available product tags: {', '.join(tags)}.\n\n"
        "A condition is either a leaf {field, operator, value} or a group "
        "{all:[...]} / {any:[...]} / {not:{...}}.\n"
        "The 'recommend' block must reference real categories/tags (or product ids) so it "
        "actually matches catalog products. Prefer tags/categories over specific product ids.\n\n"
        f"Return ONLY a JSON object shaped like:\n{json.dumps(schema, indent=2)}\n\n"
        f"Rule description: \"{text}\"\n"
        "JSON:"
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
