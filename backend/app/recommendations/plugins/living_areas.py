"""Living areas recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..types import RecommendationTier
from ..weights import derive_segment, get_weights
from .. import geo

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "living_areas.json"

# City aliases: user input -> canonical city in dataset
_CITY_ALIASES: dict[str, str] = {
    "new york": "New York",
    "new york city": "New York",
    "nyc": "New York",
    "ny": "New York",
    "united states": "New York",
    "usa": "New York",
    "us": "New York",
    "singapore": "Singapore",
    "sg": "Singapore",
    "oslo": "Oslo",
    "norway": "Oslo",
    "no": "Oslo",
    "san francisco": "San Francisco",
    "sf": "San Francisco",
    "munich": "Munich",
    "münchen": "Munich",
    "germany": "Munich",
    "de": "Munich",
}


def _resolve_city(user_city: str) -> str:
    """Map user destination to a city we have data for."""
    n = (user_city or "").split(",")[0].strip().lower()
    if not n:
        return "Singapore"
    return _CITY_ALIASES.get(n, user_city.split(",")[0].strip() or "Singapore")


# Local currency per city (dataset rent values are in local currency)
_CITY_CURRENCY: dict[str, str] = {
    "Singapore": "SGD",
    "Oslo": "NOK",
    "New York": "USD",
    "San Francisco": "USD",
    "Munich": "EUR",
}

# Approx conversion to USD for metadata (for display/comparison)
_CURRENCY_TO_USD: dict[str, float] = {
    "SGD": 0.74,
    "NOK": 0.09,
    "USD": 1.0,
    "EUR": 1.09,
}


class CommutePref(BaseModel):
    address: str = ""
    max_minutes: int = 45
    mode: str = "transit"


class LifestylePriorities(BaseModel):
    safety: int = Field(default=7, ge=0, le=10)
    nightlife: int = Field(default=5, ge=0, le=10)
    quiet: int = Field(default=6, ge=0, le=10)
    green: int = Field(default=6, ge=0, le=10)


class BudgetRange(BaseModel):
    min_val: int = Field(default=2000, alias="min", ge=0)
    max_val: int = Field(default=5000, alias="max", ge=0)

    class Config:
        populate_by_name = True


class Weights(BaseModel):
    budget: float = 0.25
    commute: float = 0.25
    space: float = 0.15
    lifestyle: float = 0.15
    rating: float = 0.1
    availability: float = 0.1


class LivingAreasCriteria(BaseModel):
    destination_city: str = "Singapore"
    budget_monthly: Dict[str, int] = Field(default_factory=lambda: {"min": 2000, "max": 5000})
    bedrooms: int = 2
    sqm_min: int = 65
    # Employee's real office coordinates (geocoded server-side from the
    # intake-captured office address). When present alongside a neighborhood's
    # coords, commute is computed for real instead of read from a static estimate.
    office_lat: Optional[float] = None
    office_lng: Optional[float] = None
    commute_work: Optional[Dict[str, Any]] = None
    commute_school: Optional[Dict[str, Any]] = None
    lifestyle_priorities: Optional[Dict[str, int]] = None
    preferred_areas: List[str] = Field(default_factory=list)
    avoid_areas: List[str] = Field(default_factory=list)
    weights: Optional[Dict[str, float]] = None


class LivingAreasPlugin(BasePlugin):
    key = "living_areas"
    title = "Living Areas"
    # Neighbourhoods are advisory content, not suppliers: rank from the static/geo
    # dataset only, never gate behind HR curation or let supplier shells shadow the
    # real rows. Housing *agencies* (the gated, RFQ-backed concept) are a separate
    # category. See the "Living Areas = 0" rework.
    advisory = True

    @property
    def CriteriaModel(self) -> type:
        return LivingAreasCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: LivingAreasCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        c = criteria
        w = c.weights or {}
        dw = get_weights("living_areas", segment=derive_segment(c))
        w_budget = w.get("budget", dw["budget"])
        w_commute = w.get("commute", dw["commute"])
        w_space = w.get("space", dw["space"])
        w_lifestyle = w.get("lifestyle", dw["lifestyle"])
        w_rating = w.get("rating", dw["rating"])
        w_avail = w.get("availability", dw["availability"])

        def _norm(s: str) -> str:
            return (s or "").split(",")[0].strip().lower()

        resolved_dest = _resolve_city(c.destination_city)
        if _norm(item.get("city", "")) != _norm(resolved_dest):
            return {"score_raw": 0, "breakdown": {}, "summary": "Wrong city", "rationale": f"Area is in {item.get('city')}, not {resolved_dest}.", "pros": [], "cons": ["Wrong city"], "metadata": {}}

        b_min = c.budget_monthly.get("min", 2000)
        b_max = c.budget_monthly.get("max", 5000)
        rent = item.get("avg_rent_2br") if c.bedrooms <= 2 else item.get("avg_rent_3br", item.get("avg_rent_2br", 3000))

        # Defense-in-depth: a foreign/supplier-shaped row (no rent data) has no
        # place in an advisory neighbourhood ranking. Score it 0 so it filters out
        # instead of raising `None > b_max` (the Living Areas = 0 crash).
        if not isinstance(rent, (int, float)) or isinstance(rent, bool):
            return {"score_raw": 0, "breakdown": {}, "summary": "No housing data",
                    "rationale": "This entry has no rent data.", "pros": [], "cons": [], "metadata": {}}

        budget_match = 100.0
        if rent > b_max:
            budget_match = max(0, 100 - 20 * (rent - b_max) / 1000)
        elif rent < b_min:
            budget_match = 90.0

        # Real commute when we have both the office coords and the neighborhood's
        # coords; otherwise fall back to the static per-row estimate (graceful
        # per-row/per-city degradation for un-geocoded data).
        commute_mins = item.get("commute_to_work_minutes_estimate", 30)
        mode = (c.commute_work or {}).get("mode", "transit") if c.commute_work else "transit"
        if (
            c.office_lat is not None and c.office_lng is not None
            and item.get("lat") is not None and item.get("lng") is not None
        ):
            est = geo.commute_minutes((c.office_lat, c.office_lng), (item["lat"], item["lng"]), mode)
            if est is not None:
                commute_mins = int(round(est))
        max_mins = 45
        if c.commute_work:
            max_mins = c.commute_work.get("max_minutes", 45)
        commute_match = max(0, 100 - (commute_mins - max_mins) * 3) if commute_mins > max_mins else 100.0

        sqm_range = item.get("typical_sqm_range", [60, 90])
        sqm_min_item = sqm_range[0] if isinstance(sqm_range, list) else 60
        space_match = 100.0 if sqm_min_item >= c.sqm_min else max(0, 100 * sqm_min_item / c.sqm_min)

        tags = item.get("tags", {})
        lp = c.lifestyle_priorities or {}
        lifestyle_match = 80.0
        if tags:
            s = sum(abs(tags.get(k, 5) - lp.get(k, 5)) for k in ["safety", "nightlife", "quiet", "green"])
            lifestyle_match = max(0, 100 - s * 3)

        rating = item.get("rating", 4.0)
        rating_score = rating * 20.0

        avail = item.get("availability_level", "medium")
        avail_map = {"high": 100, "medium": 75, "low": 50, "scarce": 25}
        availability_score = avail_map.get(avail, 50)

        score_raw = (
            w_budget * budget_match
            + w_commute * commute_match
            + w_space * space_match
            + w_lifestyle * lifestyle_match
            + w_rating * rating_score
            + w_avail * availability_score
        )

        # Preferred / avoid neighbourhoods the employee named (by area name). Additive
        # nudge, never a hard filter — an avoided area still appears, just ranked lower.
        item_name = (item.get("name") or "").strip().lower()

        def _named(names: List[str]) -> bool:
            return any(item_name and n.strip().lower() in item_name for n in (names or []))

        preferred_hit = _named(c.preferred_areas)
        avoid_hit = _named(c.avoid_areas)
        if preferred_hit:
            score_raw += 15
        if avoid_hit:
            score_raw = max(0, score_raw - 20)

        # Rationale cites the employee's own inputs (product facts — no decision/status
        # framing, keeping the compliance guard green).
        rationale_parts = [
            f"Budget: {'within' if b_min <= rent <= b_max else 'above'} the range you entered.",
            f"~{commute_mins} min by {mode} to your office.",
        ]
        if c.lifestyle_priorities:
            top = [k for k, v in c.lifestyle_priorities.items() if v >= 7]
            if top:
                rationale_parts.append(f"Matches your priorities: {', '.join(top)}.")
        if preferred_hit:
            rationale_parts.append("A neighbourhood you said you'd prefer.")
        if avoid_hit:
            rationale_parts.append("You asked to avoid this area.")
        if avail in ("low", "scarce"):
            nd = item.get("next_available_days", 30)
            rationale_parts.append(f"⚠ Scarcity: next available in ~{nd} days.")
        rationale = " ".join(rationale_parts)

        item_city = (item.get("city") or "Singapore").strip()
        currency = _CITY_CURRENCY.get(item_city, "SGD")
        pros = [f"Rating {rating}/5", f"~{commute_mins} min commute"]
        if rent <= b_max:
            pros.append(f"Within budget ({currency} {rent}/mo)")
        cons = []
        if avail in ("low", "scarce"):
            cons.append("Limited availability")
        if rent > b_max:
            cons.append("Above budget")

        return {
            "score_raw": score_raw,
            "breakdown": {
                "budget": budget_match,
                "commute": commute_match,
                "space": space_match,
                "lifestyle": lifestyle_match,
                "rating": rating_score,
                "availability": availability_score,
            },
            "summary": f"{item.get('name')} — {currency} {rent}/mo, ~{commute_mins} min commute, {rating}/5.",
            "rationale": rationale,
            "pros": pros,
            "cons": cons,
            "metadata": {
                "rating": rating,
                "rating_count": item.get("rating_count", 0),
                "availability_level": avail,
                "next_available_days": item.get("next_available_days"),
                "confidence": item.get("confidence", 80),
                "estimated_cost_usd": int(rent * _CURRENCY_TO_USD.get(currency, 1.0)),
                "estimated_cost_local": rent,
                "currency": currency,
                "cost_type": "monthly",
                "map_query": f"{item.get('name', '')}, {item.get('city', 'Singapore')}",
                # Coords for the neighborhood map (Phase 2); null until geocoded.
                "lat": item.get("lat"),
                "lng": item.get("lng"),
            },
        }
