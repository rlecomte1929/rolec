"""Housing agencies recommendation plugin.

Housing *agencies* are the gated, RFQ-backed counterpart to the advisory
neighbourhood overview (`living_areas`). They are real suppliers sourced from the
supplier registry and filtered through HR curation like movers/banks — so this
plugin is NOT advisory (it inherits the default `advisory = False`).

Two sub-types the employee can toggle, carried on the capability's
`specialization_tags` and surfaced on each item's metadata:
  * ``serviced_apartment`` — temporary / short-stay housing
  * ``rental_agency``      — permanent rental agencies

The toggle is a soft signal (an additive boost for the matching sub-type), never a
hard filter, so both sub-types stay reachable. Agencies are registry-only; there is
no static dataset (an empty file would just add a maintenance burden), so
``load_dataset`` returns [] and all candidates come from the registry.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin

# Sub-type tags (also the values HR/admin curate on the capability).
TEMPORARY_TAG = "serviced_apartment"
PERMANENT_TAG = "rental_agency"
_SUBTYPE_TAGS = {"temporary": TEMPORARY_TAG, "permanent": PERMANENT_TAG}


class HousingAgenciesCriteria(BaseModel):
    destination_city: str = ""
    destination_country: str = ""
    budget_monthly: Dict[str, int] = Field(default_factory=lambda: {"min": 2000, "max": 5000})
    # Employee's sub-type preference: "temporary" | "permanent" | None (no preference).
    subtype_preference: Optional[str] = None
    weights: Optional[Dict[str, float]] = None


def _subtype_of(tags: List[str]) -> Optional[str]:
    """Map an agency's specialization tags to a human sub-type label."""
    lowered = {str(t).strip().lower() for t in (tags or [])}
    if TEMPORARY_TAG in lowered:
        return "temporary"
    if PERMANENT_TAG in lowered:
        return "permanent"
    return None


class HousingAgenciesPlugin(BasePlugin):
    key = "housing_agencies"
    title = "Housing Agencies"
    # advisory = False (inherited): registry-backed + HR-gated, like movers.

    @property
    def CriteriaModel(self) -> type:
        return HousingAgenciesCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        # Registry-only: candidates come from the supplier registry, not a static file.
        return []

    def score(self, criteria: HousingAgenciesCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        c = criteria
        w = c.weights or {}
        tags = item.get("specialization_tags") or []
        subtype = _subtype_of(tags)

        rating = item.get("rating", 4.0)
        rating_score = rating * 20.0

        avail = item.get("availability_level", "high")
        avail_map = {"high": 100, "medium": 75, "low": 50, "scarce": 25}
        availability_score = avail_map.get(avail, 75)

        # Sub-type match is a SOFT boost, never a filter: when the employee expressed a
        # preference, an agency of that sub-type gets a bump; others still rank and show.
        subtype_match = 100.0
        if c.subtype_preference and subtype:
            subtype_match = 100.0 if subtype == c.subtype_preference else 70.0

        w_rating = w.get("rating", 0.5)
        w_avail = w.get("availability", 0.2)
        w_subtype = w.get("subtype", 0.3)
        score_raw = (
            w_rating * rating_score
            + w_avail * availability_score
            + w_subtype * subtype_match
        )

        subtype_label = {"temporary": "Serviced apartments (temporary)",
                         "permanent": "Rental agency (permanent)"}.get(subtype, "Housing agency")
        pros = [f"Rating {rating}/5", subtype_label]
        return {
            "score_raw": score_raw,
            "breakdown": {
                "rating": rating_score,
                "availability": availability_score,
                "subtype_match": subtype_match,
            },
            "summary": f"{item.get('name')} — {subtype_label}, {rating}/5.",
            "rationale": f"{subtype_label} serving {c.destination_city or 'your destination'}.",
            "pros": pros,
            "cons": [],
            "metadata": {
                "rating": rating,
                "rating_count": item.get("rating_count", 0),
                "availability_level": avail,
                "confidence": item.get("confidence", 85),
                "housing_subtype": subtype,          # "temporary" | "permanent" | None
                "specialization_tags": tags,
                "cost_type": "service",
            },
        }
