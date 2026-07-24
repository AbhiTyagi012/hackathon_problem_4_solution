"""Deterministic, offline fallbacks used when Grok is unavailable.

These keep every LLM-backed feature working (in a simpler form) with no API key or
network, so the demo never hard-fails. They are intentionally rule-of-thumb.
"""
from __future__ import annotations

_INTEREST_TAGS = {
    "gaming": ["gaming"],
    "music": ["audio", "music"],
    "audio": ["audio"],
    "fitness": ["fitness", "sports"],
    "sports": ["sports", "fitness"],
    "beauty": ["beauty"],
    "skincare": ["beauty"],
    "travel": ["travel"],
    "reading": ["books"],
    "books": ["books"],
    "cooking": ["kitchen"],
    "home": ["home"],
}


def nl_to_rule(text: str, categories: list[str], tags: list[str]) -> dict:
    """Very small keyword parser -> a rule targeting matched purchase_tags/tags."""
    lowered = text.lower()
    matched_tags = sorted({t for t in tags if t.lower() in lowered})
    matched_categories = sorted({c for c in categories if c.lower() in lowered})
    interest = next((k for k in _INTEREST_TAGS if k in lowered), None)
    if interest and not matched_tags:
        matched_tags = _INTEREST_TAGS[interest]

    if interest:
        condition = {"field": "purchase_tags", "operator": "any_in", "value": [interest]}
    elif "budget" in lowered or "cheap" in lowered or "affordable" in lowered:
        condition = {"field": "budget_band", "operator": "equals_ci", "value": "low"}
        matched_tags = matched_tags or ["budget"]
    else:
        condition = {"field": "purchase_tags", "operator": "any_in", "value": matched_tags or ["gaming"]}

    return {
        "name": (text[:40] + "…") if len(text) > 40 else text,
        "description": f"Auto-generated from: {text}",
        "priority": 75,
        "condition": condition,
        "recommend": {
            "products": [],
            "categories": matched_categories,
            "tags": matched_tags or ["gaming"],
            "score": 2.0,
        },
    }


def review_rules(rules: list[dict]) -> str:
    lines = [f"Reviewed {len(rules)} rules (offline heuristic):"]
    seen_fields: dict[str, list[str]] = {}
    for r in rules:
        cond = r.get("condition", {})
        field = cond.get("field") or next(iter(cond.keys()), "group")
        seen_fields.setdefault(str(field), []).append(r.get("id", r.get("name", "?")))
    for field, ids in seen_fields.items():
        if len(ids) > 1:
            lines.append(f"- Multiple rules key off '{field}': {', '.join(ids)} — check for overlap.")
    disabled = [r.get("id") for r in rules if not r.get("enabled", True)]
    if disabled:
        lines.append(f"- Disabled rules never fire: {', '.join(map(str, disabled))}.")
    lines.append("- Tip: ensure every common interest has at least one enabled rule.")
    return "\n".join(lines)


def suggest_product_for_rule(rule: dict) -> dict:
    rec = rule.get("recommend", {})
    tags = rec.get("tags") or ["general"]
    categories = rec.get("categories") or ["misc"]
    return {
        "name": f"New {tags[0].title()} Product",
        "category": categories[0],
        "price": 49.0,
        "brand": "House",
        "tags": tags,
        "description": f"A product added to satisfy rule '{rule.get('name', rule.get('id'))}'.",
    }
