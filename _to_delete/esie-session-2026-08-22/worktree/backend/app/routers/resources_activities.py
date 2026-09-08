"""
City-level activity suggestions for the Resources page (AIQ-1581).

  GET /api/resources/city-activities?city=&country=

Returns ~5-8 LLM-generated "things to do" suggestions for a destination. Used by
both the employee and HR Resources pages to replace the dead-end "city items are
thin" banner with an actual feed. Fail-soft: any generation error returns a 200
with an empty list so the UI degrades gracefully.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_hr_or_employee
from ..services.city_activities_service import get_city_activities

router = APIRouter(prefix="/api/resources", tags=["resources"])
log = logging.getLogger(__name__)


@router.get("/city-activities")
async def city_activities(
    city: str = Query("", description="Destination city name"),
    country: str = Query("", description="Destination country (name or ISO code)"),
    _user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """Return LLM-generated activity suggestions for (city, country).

    City and country are non-personal, so no PII masking is applied. Always
    returns 200; on any generation failure the list is empty.
    """
    activities = await get_city_activities(city=city, country=country)
    return {"city": city, "country": country, "activities": activities}
