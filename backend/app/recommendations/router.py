"""FastAPI router for recommendations API."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from .engine import recommend

log = logging.getLogger(__name__)
from .registry import get_plugin, list_categories
from .types import RecommendationResponse

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/categories")
def get_categories():
    """List all recommendation categories with schema info."""
    return {"categories": list_categories()}


@router.get("/{category}/schema")
def get_schema(category: str):
    """Get JSON schema for category criteria."""
    plugin = get_plugin(category)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Category not found: {category}")
    return plugin.CriteriaModel.model_json_schema()


class RecommendRequest:
    def __init__(self, criteria: Dict[str, Any], top_n: Optional[int] = None):
        self.criteria = criteria
        self.top_n = top_n or 10


DESTINATION_REQUIRING = ("living_areas", "schools", "movers")


@router.post("/{category}", response_model=RecommendationResponse)
def post_recommend(category: str, body: Dict[str, Any], request: Request):
    """Get recommendations for a category."""
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    start = time.perf_counter()
    plugin = get_plugin(category)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Category not found: {category}")
    criteria = body.get("criteria", {})
    top_n = body.get("top_n", 10)
    if not isinstance(criteria, dict):
        raise HTTPException(status_code=400, detail="criteria must be an object")
    dest_city = (criteria.get("destination_city") or "").strip()
    if category in DESTINATION_REQUIRING and not dest_city:
        log.warning(
            "request_id=%s category=%s recommendations_load rejected_missing_destination",
            request_id, category,
        )
        raise HTTPException(
            status_code=400,
            detail="destination_city is required for this category. Please complete your preferences with a destination city.",
        )
    try:
        result = recommend(category, criteria, top_n=int(top_n))
        dur_ms = (time.perf_counter() - start) * 1000
        dest = (criteria.get("destination_city") or "").strip()
        log.info(
            "request_id=%s category=%s dest_city=%s recommendations_load succeeded dur_ms=%.2f",
            request_id, category, dest or "(none)", dur_ms,
        )
        return result
    except Exception as e:
        dur_ms = (time.perf_counter() - start) * 1000
        log.warning(
            "request_id=%s category=%s recommendations_load failed dur_ms=%.2f error=%s",
            request_id, category, dur_ms, str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
