"""Recommendation engine orchestration."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .registry import get_plugin
from .types import (
    AvailabilityLevel,
    RecommendationItem,
    RecommendationResponse,
    RecommendationTier,
)


def recommend(
    category: str,
    criteria: Dict[str, Any],
    top_n: int = 10,
) -> RecommendationResponse:
    """Run recommendation for a category with given criteria."""
    plugin = get_plugin(category)
    if not plugin:
        raise ValueError(f"Unknown category: {category}")

    criteria_obj = plugin.validate_and_parse(criteria)
    dataset = plugin.load_dataset()

    scored_items: List[Dict[str, Any]] = []
    for item in dataset:
        result = plugin.score(criteria_obj, item)
        scored_items.append({
            "item": item,
            **result,
        })

    raw_scores = [s["score_raw"] for s in scored_items]
    norm_scores = plugin.normalize(raw_scores)

    for i, sc in enumerate(scored_items):
        sc["norm_score"] = norm_scores[i] if i < len(norm_scores) else 0
        sc["tier"] = plugin.tier(sc["norm_score"])

    scored_items.sort(key=lambda x: x["norm_score"], reverse=True)
    top = scored_items[:top_n]

    items: List[RecommendationItem] = []
    for t in top:
        item = t["item"]
        avail = t.get("metadata", {}).get("availability_level", "high")
        try:
            avail_enum = AvailabilityLevel(avail) if avail else AvailabilityLevel.MEDIUM
        except ValueError:
            avail_enum = AvailabilityLevel.MEDIUM

        rec = RecommendationItem(
            item_id=item.get("item_id", ""),
            name=item.get("name", ""),
            score=round(t["norm_score"], 1),
            tier=t["tier"],
            summary=t.get("summary", ""),
            rationale=t.get("rationale", ""),
            breakdown=t.get("breakdown", {}),
            pros=t.get("pros", []),
            cons=t.get("cons", []),
            metadata={
                **(t.get("metadata") or {}),
                "availability_level": avail,
            },
        )
        items.append(rec)

    criteria_echo = _sanitize_criteria(criteria)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return RecommendationResponse(
        category=category,
        generated_at=generated_at,
        criteria_echo=criteria_echo,
        recommendations=items,
    )


def _sanitize_criteria(criteria: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields from criteria echo."""
    skip = {"password", "token", "secret"}
    out = {}
    for k, v in criteria.items():
        if k.lower() in skip:
            continue
        if isinstance(v, dict):
            out[k] = _sanitize_criteria(v)
        else:
            out[k] = v
    return out
