"""Living areas recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..types import RecommendationTier

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "living_areas.json"


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
    commute_work: Optional[Dict[str, Any]] = None
    commute_school: Optional[Dict[str, Any]] = None
    lifestyle_priorities: Optional[Dict[str, int]] = None
    preferred_areas: List[str] = Field(default_factory=list)
    avoid_areas: List[str] = Field(default_factory=list)
    weights: Optional[Dict[str, float]] = None


class LivingAreasPlugin(BasePlugin):
    key = "living_areas"
    title = "Living Areas"

    @property
    def CriteriaModel(self) -> type:
        return LivingAreasCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: LivingAreasCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        c = criteria
        w = c.weights or {}
        w_budget = w.get("budget", 0.25)
        w_commute = w.get("commute", 0.25)
        w_space = w.get("space", 0.15)
        w_lifestyle = w.get("lifestyle", 0.15)
        w_rating = w.get("rating", 0.1)
        w_avail = w.get("availability", 0.1)

        if item.get("city", "").lower() != c.destination_city.lower():
            return {"score_raw": 0, "breakdown": {}, "summary": "Wrong city", "rationale": f"Area is in {item.get('city')}, not {c.destination_city}.", "pros": [], "cons": ["Wrong city"], "metadata": {}}

        b_min = c.budget_monthly.get("min", 2000)
        b_max = c.budget_monthly.get("max", 5000)
        rent = item.get("avg_rent_2br") if c.bedrooms <= 2 else item.get("avg_rent_3br", item.get("avg_rent_2br", 3000))

        budget_match = 100.0
        if rent > b_max:
            budget_match = max(0, 100 - 20 * (rent - b_max) / 1000)
        elif rent < b_min:
            budget_match = 90.0

        commute_mins = item.get("commute_to_work_minutes_estimate", 30)
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

        rationale_parts = [
            f"Budget: {'within' if b_min <= rent <= b_max else 'above'} your range.",
            f"Commute ~{commute_mins} min.",
            f"Lifestyle: safety {tags.get('safety', 7)}, green {tags.get('green', 6)}.",
        ]
        if avail in ("low", "scarce"):
            nd = item.get("next_available_days", 30)
            rationale_parts.append(f"⚠ Scarcity: next available in ~{nd} days.")
        rationale = " ".join(rationale_parts)

        pros = [f"Rating {rating}/5", f"~{commute_mins} min commute"]
        if rent <= b_max:
            pros.append(f"Within budget (SGD {rent}/mo)")
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
            "summary": f"{item.get('name')} — SGD {rent}/mo, ~{commute_mins} min commute, {rating}/5.",
            "rationale": rationale,
            "pros": pros,
            "cons": cons,
            "metadata": {
                "rating": rating,
                "rating_count": item.get("rating_count", 0),
                "availability_level": avail,
                "next_available_days": item.get("next_available_days"),
                "confidence": item.get("confidence", 80),
            },
        }
