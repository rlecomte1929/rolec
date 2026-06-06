"""
AIQ-40-A · HR vendor directory

GET  /api/hr/vendors            — list vendors, filterable by corridor + category
GET  /api/hr/vendors/{id}       — single vendor detail
GET  /api/hr/vendors/corridors  — corridor codes for the filter UI (live-derived)

Corridor format: "{origin_iso2}-{dest_iso2}"  e.g. "FR-DE"
Service categories:
  housing | immigration | moving | school_search | destination

Visibility:
  - Vendors are global: the live `vendors` table has no org_id column. Every
    active vendor is visible to all authenticated HR/Admin users. (The earlier
    org-scoped model was never built; see the schema-alignment fix in #405.)
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

# Fallback only — the live dropdown is derived from vendors.corridor_codes in
# list_corridors(). This static list is used solely when that query fails, so
# the filter is never empty.
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
    Return the corridor codes for the vendor filter dropdown.

    Derived from the live `vendors.corridor_codes` so the list stays in sync as
    vendor coverage changes — the old hardcoded KNOWN_CORRIDORS went stale the
    moment new corridors shipped (it listed only EU↔US pairs we no longer lead
    with). Wildcard coverage markers (e.g. "GB-*", "*") are excluded; only
    concrete ISO2 pairs are offered. Falls back to KNOWN_CORRIDORS if the query
    fails so the dropdown is never empty.
    """
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT c AS corridor
                    FROM vendors v, unnest(coalesce(v.corridor_codes, '{}')) AS c
                    WHERE v.is_active = true
                      AND c ~ '^[A-Z]{2}-[A-Z]{2}$'
                    ORDER BY corridor
                    """
                )
            ).scalars().all()
        corridors = [str(r) for r in rows]
        if corridors:
            return {"corridors": corridors}
    except Exception:
        logger.exception("list_corridors: query failed, falling back to static list")
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

    # Schema note: the live `vendors` table uses is_active / corridor_codes /
    # email / countries_served and has no org_id (vendors are global). Alias the
    # renamed columns so _row_to_vendor + the frontend keep their field names.
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, name, service_types,
                       countries_served AS countries, corridor_codes AS corridors,
                       email AS contact_email, is_active, category, is_preferred, created_at
                FROM vendors
                WHERE id = :id
                  AND is_active = true
                """
            ),
            {"id": vendor_id},
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
    _require_hr(user)  # authorise (HR/Admin); vendors are global, not org-scoped

    # Schema note: the live `vendors` table uses is_active / corridor_codes /
    # service_types / countries_served / email — no status/is_approved/org_id.
    conditions = ["v.is_active = true"]
    params: Dict[str, Any] = {}

    if corridor:
        # Match vendors that list this corridor OR have empty/global coverage.
        conditions.append(
            "(:corridor = ANY(v.corridor_codes) OR array_length(v.corridor_codes, 1) IS NULL OR array_length(v.corridor_codes, 1) = 0)"
        )
        params["corridor"] = corridor

    if category:
        conditions.append(":category = ANY(v.service_types)")
        params["category"] = category

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT v.id, v.name, v.service_types,
               v.countries_served AS countries, v.corridor_codes AS corridors,
               v.email AS contact_email, v.is_active, v.category, v.is_preferred, v.created_at
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
