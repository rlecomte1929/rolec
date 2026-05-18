"""
AIQ-40-A · HR vendor directory

GET  /api/hr/vendors            — list vendors, filterable by corridor + category
GET  /api/hr/vendors/{id}       — single vendor detail
GET  /api/hr/vendors/corridors  — return known corridor codes for the filter UI

Corridor format: "{origin_iso2}-{dest_iso2}"  e.g. "FR-DE"
Service categories:
  housing | immigration | moving | school_search | destination

Visibility:
  - Global vendors  (org_id IS NULL)  are visible to all authenticated HR users.
  - Org-scoped vendors (org_id = company_id) are visible only to that org.
  - RLS on the vendors table enforces this at DB level; the router re-applies
    the filter in Python for defence-in-depth.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db
from ...schemas import UserRole

router = APIRouter(tags=["hr_vendors"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_CORRIDORS = [
    "FR-DE",   # France → Germany
    "DE-US",   # Germany → United States
    "US-FR",   # United States → France
    "DE-FR",   # Germany → France
    "US-DE",   # United States → Germany
    "FR-US",   # France → United States
]

SERVICE_CATEGORIES = [
    "housing",
    "immigration",
    "moving",
    "school_search",
    "destination",
]


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _require_hr(user: Dict[str, Any]) -> str:
    """Assert caller is HR or Admin; return their company_id."""
    role = (user.get("role") or "").upper()
    if role not in (UserRole.HR.value, UserRole.ADMIN.value) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")

    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company") or ""
    return company_id


# ---------------------------------------------------------------------------
# Row normaliser
# ---------------------------------------------------------------------------

def _row_to_vendor(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for arr_col in ("service_types", "countries", "corridors", "service_categories"):
        val = d.get(arr_col)
        if val is None:
            d[arr_col] = []
        elif isinstance(val, str):
            # Postgres returns arrays as Python list; SQLite may return string
            if val.startswith("{") and val.endswith("}"):
                inner = val[1:-1]
                d[arr_col] = [s.strip().strip('"') for s in inner.split(",") if s.strip()] if inner else []
            else:
                d[arr_col] = [val] if val else []
        # else: already a list
    # Expose service_types as service_categories for frontend compatibility
    d["service_categories"] = d.get("service_types", [])
    for ts_col in ("created_at",):
        v = d.get(ts_col)
        if hasattr(v, "isoformat"):
            d[ts_col] = v.isoformat()
    return d


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/hr/vendors/corridors")
def list_corridors(
    _user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return the set of known corridor codes.
    Used by the frontend to populate the corridor filter dropdown.
    """
    return {"corridors": KNOWN_CORRIDORS}


@router.get("/api/hr/vendors/{vendor_id}")
def get_vendor(
    vendor_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Fetch a single vendor by ID.
    The caller must be HR/Admin and the vendor must be visible to their org.
    """
    company_id = _require_hr(user)

    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, name, service_types, countries, corridors,
                       contact_email, status, is_approved, org_id, created_at
                FROM vendors
                WHERE id = :id
                  AND status = 'active'
                  AND is_approved = true
                  AND (org_id IS NULL OR org_id = :company)
                """
            ),
            {"id": vendor_id, "company": company_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return _row_to_vendor(row)


@router.get("/api/hr/vendors")
def list_vendors(
    corridor: Optional[str] = Query(
        None,
        description='Filter by corridor, e.g. "FR-DE". Omit for all corridors.',
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by service category slug, e.g. 'housing'. Omit for all categories.",
    ),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    List vendors visible to the caller's HR org.

    Filters:
      corridor  — ISO2 pair e.g. "FR-DE". Returns vendors whose corridors array
                  contains this value OR whose corridors array is empty (global).
      category  — service_types slug. Returns vendors whose service_types array
                  contains this value.

    Returns:
      { vendors: [...], total: N, corridor: ..., category: ... }
    """
    company_id = _require_hr(user)

    # Build WHERE clauses
    conditions = [
        "v.status = 'active'",
        "v.is_approved = true",
        "(v.org_id IS NULL OR v.org_id = :company)",
    ]
    params: Dict[str, Any] = {"company": company_id}

    if corridor:
        # Match vendors that either:
        #   (a) explicitly list this corridor in their corridors array, OR
        #   (b) have an empty corridors array (treated as global coverage)
        conditions.append(
            "(:corridor = ANY(v.corridors) OR array_length(v.corridors, 1) IS NULL OR array_length(v.corridors, 1) = 0)"
        )
        params["corridor"] = corridor

    if category:
        conditions.append(":category = ANY(v.service_types)")
        params["category"] = category

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT v.id, v.name, v.service_types, v.countries, v.corridors,
               v.contact_email, v.status, v.is_approved, v.org_id, v.created_at
        FROM vendors v
        WHERE {where_sql}
        ORDER BY v.name ASC
    """

    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    vendors = [_row_to_vendor(r) for r in rows]

    return {
        "vendors": vendors,
        "total": len(vendors),
        "corridor": corridor,
        "category": category,
    }
