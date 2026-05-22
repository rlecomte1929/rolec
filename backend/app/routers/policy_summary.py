"""
[P1-5 backend] Policy & Benefits Summary API.

Returns the 14-category cap-value table for the caller's company, scoped to
the **currently published** policy_versions row. Powers the Policy Summary
tab (P1-5 frontend, AIQ-225) and is part of the propagation chain validated
by P3-5.

Endpoint
────────
GET /api/policy/summary?company_id={uuid}&tier={tier_name}

Query params
- `company_id` (required for admin; HR may omit and we use their own
  company_id from the JWT)
- `tier` (optional) — filter rows to a specific policy_tiers.name. When
  omitted, every tier's cap values are returned alongside a `tier` field
  per row.

Response shape
{
  "company_id": "…",
  "version": { id, version_number, status, effective_date, expiry_date,
               published_at, published_by },
  "status_banner": "active" | "under_review" | "expired" | "no_policy",
  "categories": [
    {
      "code": "CAT-01",
      "display_name": "Housing & Accommodation",
      "sort_order": 1,
      "rows": [
        { "tier_id", "tier_name", "cap_value", "cap_unit", "cap_currency",
          "validated_by_id", "validated_by_name", "validated_at" }
      ]
    },
    ...
  ]
}

Status banner logic
- "no_policy"      — no published version exists for this company
- "expired"        — published version has `expiry_date < today`
- "under_review"   — published version has status='in_review' OR
                     status='review_required' (P1-1 enum values)
- "active"         — everything else

All 14 canonical categories are always present in the response, even when
no policy_values rows exist for them (their `rows` array is empty). This
keeps the frontend rendering deterministic.

Standalone router — same pattern as P2-4 / P1-6 / P1-4.

Tests live in `backend/tests/test_policy_summary.py`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db


router = APIRouter(prefix="/api/policy", tags=["policy-summary"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dialect helper
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SummaryVersion(BaseModel):
    id: str
    version_number: int
    status: str
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    published_by: Optional[str] = None
    published_at: Optional[str] = None


class CategoryRow(BaseModel):
    tier_id: Optional[str] = None  # None = applies-to-all-tiers row
    tier_name: Optional[str] = None
    cap_value: Optional[float] = None
    cap_unit: Optional[str] = None
    cap_currency: str = "EUR"
    value_notes: Optional[str] = None
    validated_by_id: Optional[str] = None
    validated_by_name: Optional[str] = None
    validated_at: Optional[str] = None


class CategoryEntry(BaseModel):
    code: str
    display_name: str
    sort_order: int
    rows: List[CategoryRow]


class PolicySummaryResponse(BaseModel):
    company_id: str
    version: Optional[SummaryVersion] = None
    status_banner: str  # 'active' | 'under_review' | 'expired' | 'no_policy'
    categories: List[CategoryEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_company_id(user: Dict[str, Any], query_company_id: Optional[str]) -> str:
    """Pick the right company_id for this request and authorize.

    HR / employee → their own company_id (query override denied if mismatched).
    Admin        → uses query_company_id; required.
    """
    role = (user.get("role") or "").lower()
    user_cid = user.get("company_id")

    if role == "admin":
        if not query_company_id:
            raise HTTPException(
                status_code=400,
                detail="admin must pass ?company_id=…",
            )
        return str(query_company_id)

    if not user_cid:
        raise HTTPException(status_code=403, detail="No company_id on profile")

    if query_company_id and str(query_company_id) != str(user_cid):
        raise HTTPException(status_code=403, detail="Cross-company access denied")

    return str(user_cid)


def _load_active_version(conn: Any, company_id: str) -> Optional[Dict[str, Any]]:
    """Return the currently-published version for this company (newest
    published_at wins when there are multiple policies)."""
    row = conn.execute(
        text(
            f"SELECT v.id, v.policy_id, v.version_number, v.status, "
            f"       v.effective_date, v.expiry_date, "
            f"       v.published_by, v.published_at "
            f"FROM {_t('policy_versions')} v "
            f"JOIN {_t('company_policies')} p ON p.id = v.policy_id "
            f"WHERE p.company_id = :cid AND v.status = 'published' "
            f"ORDER BY v.published_at DESC NULLS LAST "
            f"LIMIT 1"
        ),
        {"cid": company_id},
    ).mappings().first()
    return dict(row) if row else None


def _compute_status_banner(version: Optional[Dict[str, Any]]) -> str:
    """Map version state → frontend banner key."""
    if not version:
        return "no_policy"
    status = (version.get("status") or "").lower()
    if status in ("in_review", "review_required"):
        return "under_review"
    expiry = version.get("expiry_date")
    if expiry:
        try:
            expiry_d = expiry if isinstance(expiry, date) else date.fromisoformat(str(expiry)[:10])
            if expiry_d < datetime.now(timezone.utc).date():
                return "expired"
        except Exception:
            pass
    return "active"


def _load_all_categories(conn: Any) -> List[Dict[str, Any]]:
    """Return the 14 canonical categories, sort_order ascending."""
    rows = conn.execute(
        text(
            f"SELECT id, code, display_name, sort_order "
            f"FROM {_t('policy_categories')} "
            f"ORDER BY sort_order ASC, code ASC"
        ),
    ).mappings().fetchall()
    return [dict(r) for r in rows]


def _load_values_for_version(
    conn: Any,
    *,
    version_id: str,
    tier_name: Optional[str],
) -> List[Dict[str, Any]]:
    """Return all policy_values rows for this version (optionally filtered
    by tier name) joined with category code + tier name + validator name."""
    where_tier = ""
    params: Dict[str, Any] = {"vid": version_id}
    if tier_name:
        # Optional tier filter — case-insensitive against policy_tiers.name.
        where_tier = " AND lower(pt.name) = lower(:tier_name)"
        params["tier_name"] = tier_name

    rows = conn.execute(
        text(
            f"SELECT pv.id, pv.category_id, pv.policy_tier_id, "
            f"       pv.cap_value, pv.cap_unit, pv.cap_currency, "
            f"       pv.value_notes, pv.validated_by, pv.validated_at, "
            f"       c.code AS category_code, "
            f"       pt.name AS tier_name, "
            f"       prof.full_name AS validator_name "
            f"FROM {_t('policy_values')} pv "
            f"JOIN {_t('policy_categories')} c ON c.id = pv.category_id "
            f"LEFT JOIN {_t('policy_tiers')} pt ON pt.id = pv.policy_tier_id "
            f"LEFT JOIN {_t('profiles')} prof ON prof.id = pv.validated_by "
            f"WHERE pv.version_id = :vid {where_tier}"
        ),
        params,
    ).mappings().fetchall()
    return [dict(r) for r in rows]


def _build_response(
    *,
    company_id: str,
    version: Optional[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    values: List[Dict[str, Any]],
) -> PolicySummaryResponse:
    # Group values by category code
    by_code: Dict[str, List[CategoryRow]] = {}
    for v in values:
        row = CategoryRow(
            tier_id=str(v["policy_tier_id"]) if v.get("policy_tier_id") else None,
            tier_name=v.get("tier_name"),
            cap_value=float(v["cap_value"]) if v.get("cap_value") is not None else None,
            cap_unit=v.get("cap_unit"),
            cap_currency=str(v.get("cap_currency") or "EUR"),
            value_notes=v.get("value_notes"),
            validated_by_id=str(v["validated_by"]) if v.get("validated_by") else None,
            validated_by_name=v.get("validator_name"),
            validated_at=str(v["validated_at"]) if v.get("validated_at") else None,
        )
        by_code.setdefault(str(v["category_code"]), []).append(row)

    entries: List[CategoryEntry] = [
        CategoryEntry(
            code=str(c["code"]),
            display_name=str(c["display_name"]),
            sort_order=int(c.get("sort_order") or 0),
            rows=by_code.get(str(c["code"]), []),
        )
        for c in categories
    ]

    version_dto: Optional[SummaryVersion] = None
    if version:
        version_dto = SummaryVersion(
            id=str(version["id"]),
            version_number=int(version.get("version_number") or 1),
            status=str(version.get("status") or "published"),
            effective_date=str(version["effective_date"]) if version.get("effective_date") else None,
            expiry_date=str(version["expiry_date"]) if version.get("expiry_date") else None,
            published_by=str(version["published_by"]) if version.get("published_by") else None,
            published_at=str(version["published_at"]) if version.get("published_at") else None,
        )

    return PolicySummaryResponse(
        company_id=company_id,
        version=version_dto,
        status_banner=_compute_status_banner(version),
        categories=entries,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=PolicySummaryResponse)
def get_policy_summary(
    company_id: Optional[str] = Query(None, description="Required for admin"),
    tier: Optional[str] = Query(None, description="Filter to a single tier name (case-insensitive)"),
    user: Dict[str, Any] = Depends(get_current_user),
) -> PolicySummaryResponse:
    """Return the 14-category policy summary for the caller's company."""
    resolved_company_id = _resolve_company_id(user, company_id)

    try:
        with db.engine.connect() as conn:
            version = _load_active_version(conn, resolved_company_id)
            categories = _load_all_categories(conn)
            values = (
                _load_values_for_version(
                    conn, version_id=str(version["id"]), tier_name=tier
                )
                if version
                else []
            )
    except Exception:
        logger.exception(
            "policy_summary failed company_id=%s", resolved_company_id
        )
        raise HTTPException(status_code=500, detail="Failed to load policy summary")

    return _build_response(
        company_id=resolved_company_id,
        version=version,
        categories=categories,
        values=values,
    )
