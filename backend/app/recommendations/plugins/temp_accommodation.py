"""Temporary / serviced accommodation recommendation plugin.

[ANDREA-P1] The settle-in gap the 2026-09-10 journey-completion brief called out first:
a mover on a Critical Skills permit lands in Dublin before any lease can be signed
(the letting market asks for payslips and a PPSN she cannot have yet — see the
`ie_rental_market_references_catchtwentytwo` fact). Short-stay serviced housing is the
bridge, and until now it had no category, no tile and no plugin.

Registry-backed and HR-gated like `housing_agencies` (advisory = False). Suppliers come
from the vetted registry (`platform_vetting_status='approved'`, category
`temp_accommodation`); there is no static dataset. Sub-type / area signals are carried
on `specialization_tags` the same way housing agencies carry `serviced_apartment`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..weights import derive_segment, get_weights


class TempAccommodationCriteria(BaseModel):
    destination_city: str = ""
    destination_country: str = ""
    # Nights the mover expects to bridge before permanent housing.
    stay_weeks: int = Field(default=4, ge=1, le=52)
    budget_weekly: Optional[int] = None
    # Household size drives unit size; a family of four needs a 2-bed at minimum.
    household_size: int = Field(default=1, ge=1, le=12)
    preferred_languages: List[str] = Field(default_factory=lambda: ["en"])
    weights: Optional[Dict[str, float]] = None


class TempAccommodationPlugin(BasePlugin):
    key = "temp_accommodation"
    title = "Temporary accommodation"
    # advisory = False (inherited): registry-backed + HR-gated.

    @property
    def CriteriaModel(self) -> type:
        return TempAccommodationCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        # Registry-only, deliberately (same stance as housing_agencies): a static list of
        # aparthotels would go stale and shadow the vetted registry rows.
        return []

    def score(self, criteria: TempAccommodationCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        rating = float(item.get("rating") or 4.0) * 20.0
        avail = str(item.get("availability_level") or "high")
        avail_score = {"high": 100, "medium": 75, "low": 50, "scarce": 25}.get(avail, 100)
        tags = {str(t).strip().lower() for t in (item.get("specialization_tags") or [])}
        # Family-fit: a tag like `family_units` / `two_bed` signals larger units.
        family_fit = 100.0 if criteria.household_size <= 2 or ({"family_units", "two_bed", "three_bed"} & tags) else 70.0
        # Long-stay fit: aparthotels with a `long_stay` tag suit a 4-12 week bridge better.
        stay_fit = 100.0 if criteria.stay_weeks < 4 or "long_stay" in tags else 80.0
        w = get_weights("temp_accommodation", segment=derive_segment(criteria))
        score_raw = (
            rating * w.get("rating", 0.4)
            + avail_score * w.get("availability", 0.2)
            + family_fit * w.get("family_fit", 0.2)
            + stay_fit * w.get("stay_fit", 0.2)
        )
        weeks = criteria.stay_weeks
        return {
            "score_raw": min(100.0, score_raw),
            "breakdown": {"rating": rating, "availability": avail_score, "family_fit": family_fit, "stay_fit": stay_fit},
            "summary": f"{item.get('name')} — serviced stay for ~{weeks} week(s), {item.get('rating', '—')}/5.",
            "rationale": (
                "Short-stay serviced accommodation that bridges arrival and a permanent lease; "
                "Irish landlords typically ask for payslips and a PPSN you will not hold on day one."
            ),
            "pros": [f"Rating {item.get('rating')}/5"] if item.get("rating") else [],
            "cons": [] if family_fit >= 100 else ["Unit size not confirmed for your household"],
            "metadata": {
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "availability_level": avail,
                "confidence": item.get("confidence", 80),
                "specialization_tags": sorted(tags),
            },
        }
