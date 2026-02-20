"""FastAPI router for recommendations API."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from .engine import recommend
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


@router.post("/{category}", response_model=RecommendationResponse)
def post_recommend(category: str, body: Dict[str, Any]):
    """Get recommendations for a category."""
    plugin = get_plugin(category)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Category not found: {category}")
    criteria = body.get("criteria", {})
    top_n = body.get("top_n", 10)
    if not isinstance(criteria, dict):
        raise HTTPException(status_code=400, detail="criteria must be an object")
    try:
        return recommend(category, criteria, top_n=int(top_n))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
