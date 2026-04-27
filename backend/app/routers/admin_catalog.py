"""
Admin endpoints for the master service catalog (Phase 2a).

Read-only here; Phase 2c adds the scraper-driven write endpoint and
Phase 2h adds the per-row promote/demote/remove admin UI surface.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth_deps import require_admin
from ...services import service_catalog

router = APIRouter(prefix="/api/admin/catalog", tags=["admin_catalog"])
logger = logging.getLogger(__name__)


class CatalogItemRead(BaseModel):
    id: str
    category: str
    city: Optional[str]
    country: Optional[str]
    name: str
    attributes_json: Dict[str, Any]
    source: str
    active: bool
    external_id: Optional[str]
    created_at: str
    updated_at: str
    created_by_user_id: Optional[str]


@router.get("/items", response_model=List[CatalogItemRead])
def list_catalog_items(
    category: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="One of: scraper, manual, seed, hr_promoted"),
    active_only: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    try:
        return service_catalog.list_items(
            category=category,
            city=city,
            country=country,
            source=source,
            active_only=active_only,
            limit=limit,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
