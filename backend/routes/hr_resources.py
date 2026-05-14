"""
HR Resources preview API.

Lets HR (or Admin) see exactly what an employee with a given destination +
profile would see on /resources, without needing a real assignment. Same
payload shape as /api/resources/page.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query

from ..database import db
from ..services.resources.public_service import get_resources_page_data_for_preview

router = APIRouter(prefix="/api/hr/resources", tags=["hr-resources"])


def _require_hr_or_admin(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    role = (user.get("role") or "").upper()
    if role in ("ADMIN", "HR"):
        return user
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() in ("ADMIN", "HR"):
        return user
    raise HTTPException(status_code=403, detail="HR or Admin required")


@router.get("/destinations")
def list_hr_resources_destinations(
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
) -> List[Dict[str, Any]]:
    """List all supported destinations (HR view). Alias for /api/resources/destinations."""
    from ..services import scrape_safety
    return scrape_safety.list_allowlist()


@router.get("/page")
def get_hr_resources_preview_page(
    country_code: str = Query(..., min_length=2, max_length=3, description="ISO country code, e.g. NO, FR"),
    country_name: Optional[str] = Query(None, description="Display name (optional)"),
    city: Optional[str] = Query(None, description="City name (optional)"),
    family_type: str = Query("single", pattern="^(single|couple|family)$"),
    relocation_type: str = Query("permanent", pattern="^(short_term|long_term|permanent)$"),
    has_children: Optional[bool] = Query(None),
    filters: Optional[str] = Query(None, description="JSON: city, category, audienceType, etc."),
    user: Dict[str, Any] = Depends(_require_hr_or_admin),
):
    """
    HR-only composite preview. Synthesizes ResourceContext from query params,
    then returns the same payload shape as /api/resources/page so the frontend
    can reuse rendering.
    """
    filter_dict: Dict[str, Any] = {}
    if filters:
        try:
            filter_dict = json.loads(filters)
        except json.JSONDecodeError:
            pass
    return get_resources_page_data_for_preview(
        country_code=country_code,
        country_name=country_name,
        city_name=city,
        family_type=family_type,
        relocation_type=relocation_type,
        has_children=has_children,
        filters=filter_dict,
    )
