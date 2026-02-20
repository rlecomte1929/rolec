"""Movers recommendation plugin with volume estimation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..types import RecommendationTier

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "movers.json"


def estimate_volume_m3(criteria: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate move volume from criteria."""
    acc = criteria.get("current_accommodation", {}) or {}
    acc_type = acc.get("type", "apartment")
    bedrooms = acc.get("bedrooms", 2)
    sqm = acc.get("sqm", 80)
    people = criteria.get("people", 2)
    special = criteria.get("special_items", []) or []

    base_by_type = {"studio": 15, "apartment": 25, "house": 40}
    base = base_by_type.get(acc_type, 25)
    base += (bedrooms - 1) * 8
    base += (sqm - 60) / 10 if sqm > 60 else 0
    base += (people - 1) * 3

    for s in special:
        s_lower = str(s).lower()
        if "piano" in s_lower or "grand" in s_lower:
            base += 5
        elif "bike" in s_lower or "bicycle" in s_lower:
            base += 2
        elif "fragile" in s_lower or "art" in s_lower:
            base += 1

    volume_m3 = max(5, min(60, round(base, 1)))
    if volume_m3 <= 12:
        truck = "small van"
    elif volume_m3 <= 20:
        truck = "20m3"
    else:
        truck = "40m3"
    return {"volume_m3_estimate": volume_m3, "suggested_truck_class": truck}


class MoversCriteria(BaseModel):
    origin_city: str = ""
    destination_city: str = ""
    move_type: str = "international"
    current_accommodation: Optional[Dict[str, Any]] = None
    people: int = 2
    special_items: List[str] = Field(default_factory=list)
    packing_service: str = "partial"
    storage_needed: bool = False
    preferred_move_window: Optional[Dict[str, str]] = None
    priorities: Optional[Dict[str, Any]] = None
    weights: Optional[Dict[str, float]] = None


class MoversPlugin(BasePlugin):
    key = "movers"
    title = "Movers"

    @property
    def CriteriaModel(self) -> type:
        return MoversCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: MoversCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        c = criteria
        w = c.weights or {}
        vol_info = estimate_volume_m3(c.model_dump())
        vol_est = vol_info["volume_m3_estimate"]
        max_vol = item.get("max_volume_m3", 20)
        capacity_fit = 100.0 if max_vol >= vol_est else max(0, 100 * max_vol / vol_est)

        intl = c.move_type == "international"
        intl_cap = item.get("international_capable", False)
        if intl and not intl_cap:
            capacity_fit *= 0.3
        elif intl and intl_cap:
            capacity_fit = min(100, capacity_fit * 1.1)

        lead_days = item.get("typical_lead_days", 14)
        timeline_fit = 100.0
        if c.preferred_move_window:
            timeline_fit = max(50, 100 - (lead_days - 14))

        packing = c.packing_service
        svc = item.get("services_supported", []) or []
        has_packing = "packing" in svc
        has_storage = "storage" in svc
        service_fit = 100.0
        if packing == "full" and not has_packing:
            service_fit = 50.0
        if c.storage_needed and not has_storage:
            service_fit *= 0.7

        cost_lvl = item.get("avg_cost_level", "medium")
        budget_sens = 5
        if c.priorities:
            budget_sens = c.priorities.get("budget_sensitivity", 5)
        cost_map = {"low": 100, "medium": 70, "high": 40}
        cost_score = cost_map.get(cost_lvl, 70)
        if budget_sens >= 7:
            cost_score = cost_map.get(cost_lvl, 70)
        elif budget_sens <= 3:
            cost_score = 80.0

        lang_support = 80.0
        if c.priorities and c.priorities.get("language_support"):
            langs = item.get("languages_supported", []) or []
            lang_support = 100.0 if langs else 40.0

        rating = item.get("rating", 4.0)
        rating_score = rating * 20.0
        avail = item.get("availability_level", "medium")
        avail_map = {"high": 100, "medium": 75, "low": 50, "scarce": 25}
        availability_score = avail_map.get(avail, 75)

        w_cap = w.get("cost", 0.2)
        w_time = w.get("speed", 0.2)
        w_rel = w.get("reliability", 0.2)
        w_svc = w.get("services", 0.15)
        w_rat = w.get("rating", 0.15)
        w_av = w.get("availability", 0.1)

        score_raw = (
            w_cap * capacity_fit * 0.5 + w_cap * cost_score * 0.5
            + w_time * timeline_fit
            + w_rel * rating_score * 0.5
            + w_svc * service_fit
            + w_rat * rating_score
            + w_av * availability_score
        )

        rationale = f"Volume est. {vol_est}m³ → {vol_info['suggested_truck_class']}. "
        rationale += f"Lead time ~{lead_days} days. "
        if avail in ("low", "scarce"):
            nd = item.get("next_available_days", 30)
            rationale += f"⚠ Scarcity: next slot ~{nd} days. "

        pros = [f"Rating {rating}/5", f"~{lead_days} days lead"]
        if intl_cap and intl:
            pros.append("International moves")
        cons = []
        if avail in ("low", "scarce"):
            cons.append("Limited availability")

        return {
            "score_raw": score_raw,
            "breakdown": {
                "capacity_fit": capacity_fit,
                "timeline_fit": timeline_fit,
                "service_fit": service_fit,
                "cost": cost_score,
                "language": lang_support,
                "rating": rating_score,
                "availability": availability_score,
            },
            "summary": f"{item.get('name')} — {cost_lvl} cost, ~{lead_days}d lead, {rating}/5.",
            "rationale": rationale,
            "pros": pros,
            "cons": cons,
            "metadata": {
                "rating": rating,
                "rating_count": item.get("rating_count", 0),
                "availability_level": avail,
                "next_available_days": item.get("next_available_days"),
                "confidence": item.get("confidence", 85),
                "volume_m3_estimate": vol_est,
                "suggested_truck_class": vol_info["suggested_truck_class"],
            },
        }
