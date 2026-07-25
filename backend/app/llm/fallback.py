"""Deterministic, offline fallbacks used when Groq is unavailable.

These keep every LLM-backed feature working (in a simpler form) with no API key or
network, so the demo never hard-fails. They are intentionally rule-of-thumb.
"""
from __future__ import annotations

import re


def _word_in(needle: str, haystack: str) -> bool:
    """Whole-word match, not naive substring containment.

    Plain `needle in haystack` false-positives on short tags/keywords that are
    substrings of unrelated words — e.g. the catalog tag "seat" is literally
    contained in "Seattle", "art" in "smart"/"start". That turned a location
    mention into a fabricated "seat"-tagged rule instead of correctly being
    treated as an unsupported request.
    """
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


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


def nl_to_rule(text: str, categories: list[str], tags: list[str]) -> dict | None:
    """Very small keyword parser -> a rule targeting matched purchase_tags/tags.

    Returns None when the text doesn't confidently match anything this parser
    understands, rather than guessing — e.g. random/rubbish text, or a request
    that depends on a signal outside the currently supported scope (purchase
    history/interest keywords, budget). The caller surfaces this as an explicit
    "not supported yet" response instead of fabricating a plausible-looking but
    wrong rule.
    """
    lowered = text.lower()
    matched_tags = sorted({t for t in tags if _word_in(t.lower(), lowered)})
    matched_categories = sorted({c for c in categories if _word_in(c.lower(), lowered)})
    interest = next((k for k in _INTEREST_TAGS if _word_in(k, lowered)), None)
    if interest and not matched_tags:
        matched_tags = _INTEREST_TAGS[interest]

    if interest:
        condition = {"field": "purchase_tags", "operator": "any_in", "value": [interest]}
    elif matched_tags:
        condition = {"field": "purchase_tags", "operator": "any_in", "value": matched_tags}
    elif "budget" in lowered or "cheap" in lowered or "affordable" in lowered:
        condition = {"field": "budget_band", "operator": "equals_ci", "value": "low"}
        matched_tags = matched_tags or ["budget"]
    else:
        return None

    return {
        "name": (text[:40] + "…") if len(text) > 40 else text,
        "description": f"Auto-generated from: {text}",
        "priority": 75,
        "condition": condition,
        "recommend": {
            "products": [],
            "categories": matched_categories,
            "tags": matched_tags,
            "score": 1.0,
        },
    }


def check_rule_conflicts(draft: dict, candidates: list[dict]) -> dict:
    """Coarse offline heuristic: flag overlap when the draft's condition shares
    the same field and an intersecting value with a retrieved candidate's
    condition. No semantic reasoning — just enough signal to be useful with
    zero network calls; the real (Groq) path reasons about it properly."""
    draft_cond = draft.get("condition") or {}
    draft_field = draft_cond.get("field")
    draft_value = draft_cond.get("value")
    draft_values = set(draft_value) if isinstance(draft_value, list) else {draft_value}

    flagged = []
    for c in candidates:
        cond = c.get("condition") or {}
        if not draft_field or cond.get("field") != draft_field:
            continue
        cand_value = cond.get("value")
        cand_values = set(cand_value) if isinstance(cand_value, list) else {cand_value}
        overlap = draft_values & cand_values
        if overlap:
            flagged.append(
                {
                    "rule_id": c.get("id"),
                    "note": f"same field '{draft_field}', overlapping value(s): {sorted(overlap)}",
                }
            )

    if not flagged:
        return {
            "verdict": "ok",
            "candidates": [],
            "notes": "No overlapping condition values found among retrieved candidates (offline heuristic).",
        }
    return {
        "verdict": "overlap",
        "candidates": flagged,
        "notes": f"{len(flagged)} retrieved rule(s) share the same condition field and an overlapping value (offline heuristic).",
    }


def repair_rule(draft: dict, error: str) -> dict | None:
    """No offline repair — fixing an arbitrary validation error needs real
    reasoning about the specific failure, not a heuristic. Returns None
    honestly rather than faking a fix; the caller treats this as
    'validation failed, no repair available without a live LLM'."""
    return None


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
