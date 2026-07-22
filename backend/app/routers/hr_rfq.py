"""
AIQ-40-C · RFQ (Request for Quote) flow — read-only remnant

GET  /api/hr/rfq-requests?case_id=<uuid>
  — Returns legacy rfq_requests rows for a given case.

NOTE (AIQ-1682): the HR-initiated RFQ *create* (POST) and *status update* (PATCH)
endpoints were retired as part of the two-models consolidation — RFQs are now
employee-led (canonical `rfqs`/`rfq_items`/`quotes`; see `routers/rfq.py`), with HR
acting as the payer/approver rather than originating quote requests. This GET remains
only so legacy `rfq_requests` rows stay readable until the table is archived (AIQ-1683)
and its last reader is removed (AIQ-1684).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth_deps import get_current_user
from ...database import db
from ...schemas import UserRole

router = APIRouter(tags=["hr_rfq"])
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_hr(user: Dict[str, Any]) -> tuple[str, str]:
    """Assert HR/Admin; return (company_id, user_email)."""
    role = (user.get("role") or "").upper()
    if role not in (UserRole.HR.value, UserRole.ADMIN.value) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")
    uid = user.get("id")
    profile = db.get_profile_record(uid)
    # hr_users-first: legacy/text HR ids have NULL profiles.company_id but a valid hr_users row.
    company_id = (db.get_hr_company_id(uid) if uid else None) or (profile or {}).get("company_id") or user.get("company") or ""
    email = (profile or {}).get("email") or user.get("email") or ""
    name = (
        f"{(profile or {}).get('first_name', '')} {(profile or {}).get('last_name', '')}".strip()
        or email
    )
    return company_id, email, name   # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/hr/rfq-requests")
async def list_rfqs(
    case_id: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return RFQs for a case (HR use, for AIQ-40-D pending list)."""
    company_id, _, _ = _require_hr(user)

    from sqlalchemy import text as sql_text
    conditions = ["r.org_id = :org_id"]
    params: Dict[str, Any] = {"org_id": company_id}

    if case_id:
        conditions.append("r.case_id = :case_id")
        params["case_id"] = case_id

    where = " AND ".join(conditions)
    sql = f"""
        SELECT r.id, r.case_id, r.vendor_id, r.service_category,
               r.move_date, r.budget_range, r.special_requirements,
               r.hr_email, r.hr_name, r.status, r.created_at, r.updated_at,
               v.name AS vendor_name, v.email AS vendor_email
        FROM rfq_requests r
        LEFT JOIN vendors_legacy v ON v.id = r.vendor_id  -- [AIQ-1638] vendors → vendors_legacy (renamed on prod)
        WHERE {where}
        ORDER BY r.created_at DESC
    """
    with db.engine.begin() as conn:
        rows = conn.execute(sql_text(sql), params).mappings().all()

    rfqs = []
    for row in rows:
        d = dict(row)
        for ts in ("created_at", "updated_at", "move_date"):
            v = d.get(ts)
            if hasattr(v, "isoformat"):
                d[ts] = v.isoformat()
        rfqs.append(d)

    return {"rfqs": rfqs, "total": len(rfqs)}
