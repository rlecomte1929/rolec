"""Recommendation engine orchestration."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .explanation import build_explanation
from .registry import get_plugin
from .types import (
    RecommendationExplanation,
    RecommendationItem,
    RecommendationResponse,
    RecommendationTier,
)


def _load_dataset_with_registry(category: str, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Load recommendation candidates. Supplier Registry is primary when it has data;
    static JSON is fallback when registry returns zero items.
    """
    plugin = get_plugin(category)
    static_dataset = plugin.load_dataset() if plugin else []

    registry_items: List[Dict[str, Any]] = []
    try:
        from ..db import SessionLocal
        from ..services.supplier_registry import search_by_service_destination

        dest_city = (criteria.get("destination_city") or "").strip()
        dest_country = (criteria.get("destination_country") or "").strip()
        if dest_city or dest_country:
            with SessionLocal() as session:
                registry_items = search_by_service_destination(
                    session,
                    service_category=category,
                    destination_city=dest_city or None,
                    destination_country=dest_country or None,
                    limit=50,
                )
    except Exception:
        pass

    if registry_items:
        # Registry is primary: use registry items, optionally merge non-duplicate static items
        existing_ids = {str((r.get("item_id") or "")) for r in registry_items}
        dataset = list(registry_items)
        for d in static_dataset:
            iid = str((d.get("item_id") or ""))
            if iid and iid not in existing_ids:
                dataset.append(d)
                existing_ids.add(iid)
    else:
        # Fallback: static JSON only when registry has no matching suppliers
        dataset = list(static_dataset)

    return dataset


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
    dataset = _load_dataset_with_registry(category, criteria)

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

    # Filter out items that don't match destination (score 0 = wrong city, etc.)
    matching = [s for s in scored_items if s["score_raw"] > 0]

    preferred_ids: set = set()
    for sid in (criteria.get("_preferred_supplier_ids") or []):
        if sid:
            preferred_ids.add(str(sid))

    def _is_preferred(x: Dict[str, Any]) -> bool:
        iid = str((x.get("item") or {}).get("item_id") or "")
        return iid in preferred_ids

    # Deterministic ranking: preferred first (boost), then score desc, then item_id/name asc
    PREFERRED_BOOST = 15  # Add to norm_score so preferred rank higher
    for s in matching:
        if _is_preferred(s):
            s["norm_score"] = (s.get("norm_score") or 0) + PREFERRED_BOOST
            s["_company_preferred"] = True
            s["tier"] = plugin.tier(min(100, s["norm_score"]))
        else:
            s["_company_preferred"] = False

    matching.sort(
        key=lambda x: (
            -(x.get("norm_score") or 0),
            str((x.get("item") or {}).get("item_id") or ""),
            str((x.get("item") or {}).get("name") or ""),
        )
    )
    top = matching[:top_n]

    items: List[RecommendationItem] = []
    for t in top:
        item = t["item"]
        avail = t.get("metadata", {}).get("availability_level", "high")
        company_preferred = t.get("_company_preferred", False)

        expl_dict = build_explanation(item, t, criteria, category)
        explanation = RecommendationExplanation(**expl_dict)

        rec = RecommendationItem(
            item_id=item.get("item_id", ""),
            name=item.get("name", ""),
            score=round(min(100, t["norm_score"]), 1),  # Cap score display at 100
            tier=t["tier"],
            summary=t.get("summary", ""),
            rationale=t.get("rationale", ""),
            breakdown=t.get("breakdown", {}),
            pros=t.get("pros", []),
            cons=t.get("cons", []),
            metadata={
                **(t.get("metadata") or {}),
                "availability_level": avail,
                "company_preferred": company_preferred,
            },
            explanation=explanation,
        )
        items.append(rec)

    criteria_echo = _sanitize_criteria(criteria)
    # Add office address for map directions (living areas, schools)
    dest_city = (criteria.get("destination_city") or "").strip()
    office = (criteria.get("office_address") or "").strip()
    criteria_echo["office_address"] = office or _default_office_for_city(dest_city)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return RecommendationResponse(
        category=category,
        generated_at=generated_at,
        criteria_echo=criteria_echo,
        recommendations=items,
    )


def _default_office_for_city(city: str) -> str:
    """Default office location for commute directions by city."""
    city_lower = (city or "").lower()
    defaults = {
        "singapore": "Raffles Place MRT, Singapore",
        "london": "Canary Wharf, London, UK",
        "new york": "Midtown Manhattan, New York, NY",
        "san francisco": "1 Market St, San Francisco, CA",
        "berlin": "Mitte, Berlin, Germany",
        "oslo": "Sentrum, Oslo, Norway",
    }
    return defaults.get(city_lower) or f"{city}, city center"


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
