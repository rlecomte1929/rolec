"""Movers recommendation plugin with volume estimation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..types import RecommendationTier
from ..weights import derive_segment, get_weights

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


# [AIQ-1872] Destination country -> logistics coverage region, from one source
# of truth so an ISO code and a written-out name always agree.
#
# Deliberately a MOVING-INDUSTRY coverage map, not an immigration one: it is about
# which movers plausibly serve a lane, so the UK sits in Europe and Switzerland is
# unremarkable. Do NOT swap in immigration_regime._EU_EEA_COUNTRIES — that set
# answers "does this person have free movement?", a different question with a
# different answer for the same countries.
#
# Covers the destinations the product actually serves (the readiness-template set
# plus the resource-catalog countries). An unmapped country simply yields no region
# tier, which scores as no-coverage rather than guessing a continent.
_COUNTRIES: tuple[tuple[str, str, str], ...] = (
    # (ISO-2, common name, coverage region)
    ("ie", "ireland", "europe"),
    ("gb", "united kingdom", "europe"),
    ("fr", "france", "europe"),
    ("de", "germany", "europe"),
    ("es", "spain", "europe"),
    ("it", "italy", "europe"),
    ("nl", "netherlands", "europe"),
    ("no", "norway", "europe"),
    ("dk", "denmark", "europe"),
    ("se", "sweden", "europe"),
    ("ch", "switzerland", "europe"),
    ("pt", "portugal", "europe"),
    ("be", "belgium", "europe"),
    ("at", "austria", "europe"),
    ("pl", "poland", "europe"),
    ("us", "united states", "americas"),
    ("ca", "canada", "americas"),
    ("br", "brazil", "americas"),
    ("mx", "mexico", "americas"),
    ("sg", "singapore", "asia"),
    ("hk", "hong kong", "asia"),
    ("jp", "japan", "asia"),
    ("cn", "china", "asia"),
    ("in", "india", "asia"),
    ("au", "australia", "oceania"),
    ("nz", "new zealand", "oceania"),
    ("ae", "united arab emirates", "middle_east"),
    ("za", "south africa", "africa"),
)

# Any form of a country -> its coverage region.
_COUNTRY_REGION: dict[str, str] = {
    form: region for iso, name, region in _COUNTRIES for form in (iso, name)
}

# Any form of a country -> every form of it, so an ISO code on the case matches a
# mover that wrote the country out in words. "IE" is not a substring of "Ireland",
# which is exactly how country-level coverage scored as no coverage before.
_COUNTRY_FORMS: dict[str, tuple[str, ...]] = {
    form: (iso, name) for iso, name, _ in _COUNTRIES for form in (iso, name)
}

# Cities the recommendation datasets actually carry, mapped to their region.
#
# Needed because `destination_country` is not always supplied — the frozen scoring
# baseline passes a bare `destination_city: "Tokyo"`, and so can any caller that
# builds criteria by hand. Without this, requiring a country to resolve a region
# would trade the old Asia-only bug for a country-required one: Tokyo vs ["Asia"]
# would drop from 75 to 20.
_CITY_REGION: dict[str, str] = {
    "dublin": "europe", "madrid": "europe", "munich": "europe", "oslo": "europe",
    "london": "europe", "paris": "europe", "berlin": "europe", "amsterdam": "europe",
    "copenhagen": "europe", "stavanger": "europe", "barcelona": "europe",
    "lisbon": "europe", "zurich": "europe", "milan": "europe",
    "new york": "americas", "san francisco": "americas", "toronto": "americas",
    "sao paulo": "americas", "mexico city": "americas",
    "singapore": "asia", "tokyo": "asia", "hong kong": "asia",
    "shanghai": "asia", "mumbai": "asia", "bangalore": "asia",
    "sydney": "oceania", "melbourne": "oceania", "auckland": "oceania",
    "dubai": "middle_east", "abu dhabi": "middle_east",
    "johannesburg": "africa", "cape town": "africa",
}

# Words a mover may use to describe each region's coverage.
_REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "europe": ("europe", "european", "emea", "eu"),
    "americas": ("americas", "north america", "south america", "latam", "usa", "us"),
    "asia": ("asia", "asia-pacific", "apac", "far east"),
    "oceania": ("oceania", "australasia", "asia-pacific", "apac", "anz"),
    "middle_east": ("middle east", "gulf", "gcc", "emea"),
    "africa": ("africa", "emea"),
}


def _service_area_score(
    destination_city: str,
    service_areas: List[str],
    destination_country: str = "",
) -> float:
    """Score 0–100 for how well a mover's service_areas cover the destination.

    Tiers:
    - 100: exact city name appears in service_areas (e.g. "Tokyo" for Tokyo)
    - 95:  the destination COUNTRY appears (e.g. "Ireland" for Dublin)
    - 85:  broad global coverage ("Global", "Worldwide")
    - 75:  the destination's own REGION appears (e.g. "Europe" for Dublin)
    - 20:  no relevant coverage

    [AIQ-1872] This used to know exactly one region — Asia — and only ever matched
    a city by name. The result was a dimension that was actively WRONG outside
    Asia rather than merely weak. Measured on the shipped dataset before the fix:

        Dublin vs ["Europe"]  -> 20      Dublin vs ["Asia"]   -> 75
        Dublin vs ["Ireland"] -> 20      New York vs ["Americas"] -> 20

    A mover covering Europe scored worse for a Dublin move than one covering Asia,
    and a mover covering Ireland scored as though it had no coverage at all.

    Deliberately still a SCORE and not a hard gate: the ticket warns against
    over-filtering corridors that legitimately share regional movers, and a
    coverage list is vendor-authored free text, not a guarantee. Out-of-region
    vendors are penalised, not excluded.
    """
    if not destination_city and not destination_country:
        return 50.0  # unknown destination → neutral
    dest = (destination_city or "").strip().lower()
    country = (destination_country or "").strip().lower()
    areas_lower = [a.strip().lower() for a in (service_areas or []) if a and a.strip()]
    if not areas_lower:
        return 20.0

    # Exact city match (substring in either direction)
    if dest and any(dest in a or a == dest for a in areas_lower):
        return 100.0

    # Destination country named outright, in any form we know for it.
    country_forms = _COUNTRY_FORMS.get(country, (country,)) if country else ()
    if any(f and (f in a or a == f) for a in areas_lower for f in country_forms):
        return 95.0

    # Global coverage keywords
    if any(k in a for a in areas_lower for k in ("global", "worldwide")):
        return 85.0

    # The destination's own region. Resolved from the country when we have it,
    # otherwise from the city name if it happens to be a country we know.
    region = (
        _COUNTRY_REGION.get(country)
        or _COUNTRY_REGION.get(dest)   # the "city" is actually a country name
        or _CITY_REGION.get(dest)      # a known city, when no country was supplied
    )
    if region:
        for keyword in _REGION_KEYWORDS.get(region, ()):
            if any(keyword in a for a in areas_lower):
                return 75.0

    return 20.0


class MoversCriteria(BaseModel):
    origin_city: str = ""
    destination_city: str = ""
    # [AIQ-1872] criteria_builder has always emitted `destination_country`, but this
    # model never declared it, so pydantic dropped it and the service-area scorer
    # only ever saw a city name. That is why country-level coverage ("Ireland" for
    # a Dublin move) scored as no coverage at all.
    destination_country: str = ""
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
        from_registry = item.get("_source") == "supplier_registry"
        # Registry items often lack movers-specific fields; use friendly defaults so they rank fairly
        max_vol = item.get("max_volume_m3", 40 if from_registry else 20)
        intl_cap = item.get("international_capable", True if from_registry else False)
        lead_days = item.get("typical_lead_days", 14)
        svc = item.get("services_supported", ["packing", "storage"] if from_registry else []) or []
        cost_lvl = item.get("avg_cost_level", "medium")

        vol_info = estimate_volume_m3(c.model_dump())
        vol_est = vol_info["volume_m3_estimate"]
        capacity_fit = 100.0 if max_vol >= vol_est else max(0, 100 * max_vol / vol_est)

        intl = c.move_type == "international"
        intl_hard_floor = False
        if intl and not intl_cap:
            # Hard floor: a domestic-only mover is unqualified for an international move.
            # Penalise capacity_fit for the breakdown, then cap the final score_raw ≤ 5
            # so the mover cannot creep into top ranks via other strong signals
            # (rating, cost, service area).
            capacity_fit *= 0.3
            intl_hard_floor = True
        elif intl and intl_cap:
            capacity_fit = min(100, capacity_fit * 1.1)

        timeline_fit = 100.0
        if c.preferred_move_window:
            timeline_fit = max(50, 100 - (lead_days - 14))

        packing = c.packing_service
        has_packing = "packing" in svc
        has_storage = "storage" in svc
        service_fit = 100.0
        if packing == "full" and not has_packing:
            service_fit = 50.0
        if c.storage_needed and not has_storage:
            service_fit *= 0.7

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

        service_area_score = _service_area_score(
            c.destination_city,
            item.get("service_areas") or [],
            destination_country=c.destination_country,
        )

        dw = get_weights("movers", segment=derive_segment(c))
        w_cap = w.get("cost", dw["cost"])
        w_time = w.get("speed", dw["speed"])
        w_rel = w.get("reliability", dw["reliability"])
        w_svc = w.get("services", dw["services"])
        w_rat = w.get("rating", dw["rating"])
        w_av = w.get("availability", dw["availability"])
        w_sarea = w.get("service_area", dw.get("service_area", 0.0))

        score_raw = (
            w_cap * capacity_fit * 0.5 + w_cap * cost_score * 0.5
            + w_time * timeline_fit
            + w_rel * rating_score * 0.5
            + w_svc * service_fit
            + w_rat * rating_score
            + w_av * availability_score
            + w_sarea * service_area_score
        )
        if intl_hard_floor:
            score_raw = min(score_raw, 5.0)

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
                "service_area": service_area_score,
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
                "estimated_cost_usd": int(
                    ({"high": 12000, "medium": 8000, "low": 5000}.get(
                        cost_lvl, 8000
                    ) * (vol_est / 25))
                ),
                "cost_type": "one_time",
            },
        }
