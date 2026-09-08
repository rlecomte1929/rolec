"""[Phase 3] Attach curated schools reachable from each recommended neighborhood.

For a case with school-age children, annotate living-areas recommendations with
the nearest curated schools (geocoded in Phase 1), so the housing map can show a
schools layer scoped to the neighborhoods on screen — not a generic city list.
Best-effort straight-line proximity, reusing the Phase-1 commute model.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import geo
from .plugins.living_areas import _resolve_city

SCHOOLS_PATH = Path(__file__).resolve().parent / "datasets" / "schools.json"

_SCHOOLS_CACHE: Optional[List[Dict[str, Any]]] = None


def school_age_from_draft(draft: Dict[str, Any]) -> bool:
    """True when the case likely has a school-age child (~2–18).

    Reads the intake household step: familyMembers.children[].dateOfBirth, with a
    lenient hasDependents+children fallback when no parseable DOB is present.
    """
    if not isinstance(draft, dict):
        return False
    fam = draft.get("familyMembers") or {}
    children = fam.get("children") or []
    this_year = date.today().year
    for ch in children:
        if not isinstance(ch, dict):
            continue
        dob = ch.get("dateOfBirth") or ch.get("dob")
        if isinstance(dob, str) and len(dob) >= 4 and dob[:4].isdigit():
            age = this_year - int(dob[:4])
            if 2 <= age <= 18:
                return True
    basics = draft.get("relocationBasics") or {}
    if children and (basics.get("hasDependents") or basics.get("has_dependents")):
        return True
    return False


def _load_schools() -> List[Dict[str, Any]]:
    global _SCHOOLS_CACHE
    if _SCHOOLS_CACHE is None:
        with open(SCHOOLS_PATH, encoding="utf-8") as f:
            _SCHOOLS_CACHE = json.load(f)
    return _SCHOOLS_CACHE


def _nearby(lat: float, lng: float, schools: List[Dict[str, Any]], max_minutes: float, limit: int) -> List[Dict[str, Any]]:
    scored: List[tuple[float, Dict[str, Any]]] = []
    for s in schools:
        s_lat, s_lng = s.get("lat"), s.get("lng")
        if not isinstance(s_lat, (int, float)) or not isinstance(s_lng, (int, float)):
            continue
        mins = geo.straight_line_commute_minutes((lat, lng), (s_lat, s_lng), "transit")
        if mins is None or mins > max_minutes:
            continue
        scored.append((mins, s))
    scored.sort(key=lambda t: t[0])
    return [
        {
            "item_id": s.get("item_id"),
            "name": s.get("name"),
            "type": s.get("type"),
            "curriculum": s.get("curriculum"),
            "lat": s.get("lat"),
            "lng": s.get("lng"),
            "commute_min": int(round(mins)),
        }
        for mins, s in scored[:limit]
    ]


def attach_nearby_schools(response: Any, dest_city: str, max_minutes: float = 35.0, limit: int = 4) -> None:
    """Mutate each living-areas item's metadata with a `nearby_schools` list."""
    city = _resolve_city(dest_city or "")
    schools = [s for s in _load_schools() if (s.get("city") or "").strip().lower() == city.strip().lower()]
    if not schools:
        return
    for item in getattr(response, "recommendations", []) or []:
        meta = getattr(item, "metadata", None)
        if not isinstance(meta, dict):
            continue
        lat, lng = meta.get("lat"), meta.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            nearby = _nearby(lat, lng, schools, max_minutes, limit)
            meta["nearby_schools"] = nearby
            # Multi-destination commute: a per-mode (walk/bike/transit/car) reachability
            # to the NEAREST school, mirroring the office commute. Households weigh both
            # the office and the school run; surface the school leg on the same card.
            if nearby:
                s0 = nearby[0]
                s_lat, s_lng = s0.get("lat"), s0.get("lng")
                if isinstance(s_lat, (int, float)) and isinstance(s_lng, (int, float)):
                    modes = geo.multimodal_commute((lat, lng), (s_lat, s_lng))
                    if modes:
                        meta["school_commute_modes"] = modes
                        meta["nearest_school_name"] = s0.get("name")
