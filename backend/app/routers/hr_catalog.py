"""
HR-side catalog curation endpoints (Phase 2d).

GET   /api/hr/catalog/curation         — combined view: master items
                                          for the (category, city) joined
                                          with HR's selection state
POST  /api/hr/catalog/curation/select  — bulk toggle selected on master rows
POST  /api/hr/catalog/curation/custom  — add an HR custom vendor
DELETE /api/hr/catalog/curation/custom/{id} — remove an HR custom vendor

All routes require HR or Admin and are tenant-scoped to caller's company.
Audit trail goes via the relopass_audit_row trigger on the table.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth_deps import require_admin_or_hr
from ...database import db
from ...services import service_catalog, vendor_curation

router = APIRouter(prefix="/api/hr/catalog", tags=["hr_catalog"])
logger = logging.getLogger(__name__)


def _caller_company_id(user: Dict[str, Any]) -> str:
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — HR curation needs a tenant.",
        )
    return company_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CurationRow(BaseModel):
    kind: str  # "master" | "custom"
    selection_id: Optional[str] = None
    master_item_id: Optional[str] = None
    name: str
    selected: bool
    attributes: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None  # master row source (scraper / manual / seed / hr_promoted)
    city: Optional[str] = None
    country: Optional[str] = None


class CurationView(BaseModel):
    company_id: str
    category: str
    destination_city: Optional[str]
    rows: List[CurationRow]


class SelectToggle(BaseModel):
    master_item_id: str
    selected: bool


class BulkSelectBody(BaseModel):
    category: str
    destination_city: Optional[str] = None
    country: Optional[str] = None
    toggles: List[SelectToggle]


class CustomVendorBody(BaseModel):
    category: str
    name: str = Field(..., min_length=1, max_length=200)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    destination_city: Optional[str] = None
    country: Optional[str] = None
    display_order: int = 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/curation", response_model=CurationView)
def get_curation_view(
    category: str = Query(..., min_length=1),
    destination_city: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Combined view HR uses to curate one category × city. Returns:
    - Every admin master item for (category, city) with the HR selection state
      attached (or "selected=true" by default if HR hasn't decided yet).
    - Every HR custom vendor row for the same scope.
    """
    company_id = _caller_company_id(user)
    # Match the master plugins' geo-bound vs geo-agnostic split: when the
    # category has no rows tagged with a city, every row applies everywhere
    # (e.g. movers / banks). Filtering strictly on city would hide them and
    # leave HR with "0 items" for categories that in fact have a full list.
    all_active = service_catalog.list_items(
        category=category,
        active_only=True,
        limit=200,
    )
    has_geo_rows = any(m.get("city") for m in all_active)
    if has_geo_rows and destination_city:
        master_items = [m for m in all_active if m.get("city") == destination_city]
    else:
        master_items = all_active
    selections = vendor_curation.list_curation(
        company_id=company_id,
        category=category,
        destination_city=destination_city,
    )

    # Index HR selections by master_item_id (master toggles) and a list of customs.
    selection_by_master: Dict[str, Dict[str, Any]] = {}
    customs: List[Dict[str, Any]] = []
    for s in selections:
        if s.get("master_item_id"):
            selection_by_master[s["master_item_id"]] = s
        elif s.get("custom_item_json"):
            customs.append(s)

    rows: List[CurationRow] = []
    for m in master_items:
        sel = selection_by_master.get(m["id"])
        rows.append(
            CurationRow(
                kind="master",
                selection_id=sel.get("id") if sel else None,
                master_item_id=m["id"],
                name=m["name"],
                # Default to False (hidden) until HR explicitly approves —
                # the strict authority model: "the employee can only pick
                # from the list pre-selected and validated by HR." Until HR
                # ticks an item, the employee does not see it. The empty
                # employee state is rendered as "HR is finalizing providers"
                # by Phase 2c's filter.
                selected=bool(sel["selected"]) if sel else False,
                attributes=m.get("attributes_json") or {},
                source=m.get("source"),
                city=m.get("city"),
                country=m.get("country"),
            )
        )
    for c in customs:
        payload = c.get("custom_item_json") or {}
        rows.append(
            CurationRow(
                kind="custom",
                selection_id=c["id"],
                master_item_id=None,
                name=str(payload.get("name") or "(unnamed)"),
                selected=bool(c["selected"]),
                attributes={k: v for k, v in payload.items() if k != "name"},
                source=None,
                city=c.get("destination_city"),
                country=c.get("country"),
            )
        )
    return {
        "company_id": company_id,
        "category": category,
        "destination_city": destination_city,
        "rows": [r.model_dump() for r in rows],
    }


@router.post("/curation/select")
def bulk_select(
    body: BulkSelectBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Toggle selected on/off for one or more master rows in one call."""
    company_id = _caller_company_id(user)
    actor_id = user["id"]
    updated = []
    for t in body.toggles:
        row = vendor_curation.upsert_master_selection(
            company_id=company_id,
            category=body.category,
            master_item_id=t.master_item_id,
            selected=t.selected,
            destination_city=body.destination_city,
            country=body.country,
            actor_user_id=actor_id,
        )
        updated.append(row)
    return {"updated": len(updated), "rows": updated}


@router.post("/curation/custom")
def add_custom(
    body: CustomVendorBody,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """HR adds a vendor not in the admin master."""
    company_id = _caller_company_id(user)
    actor_id = user["id"]
    try:
        row = vendor_curation.add_custom_vendor(
            company_id=company_id,
            category=body.category,
            name=body.name,
            attributes=body.attributes,
            destination_city=body.destination_city,
            country=body.country,
            display_order=body.display_order,
            actor_user_id=actor_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return row


@router.delete("/curation/custom/{row_id}")
def delete_custom(
    row_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    company_id = _caller_company_id(user)
    try:
        ok = vendor_curation.delete_custom_vendor(company_id=company_id, row_id=row_id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    if not ok:
        raise HTTPException(status_code=404, detail="Custom vendor not found")
    return {"deleted": True, "id": row_id}
