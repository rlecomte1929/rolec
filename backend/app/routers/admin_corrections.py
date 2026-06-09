"""Correction analytics API — AIQ-554 / C2-03.

GET /api/admin/corrections/by-reason
    Weekly counts of human corrections grouped by reason_code, case_corridor,
    and clause_type. Respects HR scoping (own employer) with an admin override
    to view across all employers.

Auth: admin or HR (``require_admin_or_hr``). HR callers are pinned to their own
employer; admins without a linked company aggregate across all employers, and
may narrow with the optional ``employer_id`` query param.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth_deps import require_admin_or_hr
from ...database import db
from ..services.correction_analytics import (
    summarize_by_reason,
    weekly_corrections_by_reason,
)

router = APIRouter(prefix="/api/admin/corrections", tags=["admin-corrections"])
logger = logging.getLogger(__name__)


def _caller_company_id(user: Dict[str, Any]) -> Optional[str]:
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    return str(company_id) if company_id else None


@router.get("/by-reason")
def corrections_by_reason(
    employer_id: Optional[str] = Query(
        None,
        description="Admin-only override to scope to a single employer. "
        "Ignored for HR callers (always pinned to their own employer).",
    ),
    weeks_back: int = Query(4, ge=1, le=52),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Weekly correction counts grouped by reason_code, corridor, and clause_type."""
    is_admin = bool(user.get("is_admin"))
    caller_company = _caller_company_id(user)

    if is_admin:
        # Admin may override; falling back to None means "all employers".
        scope_employer_id = employer_id or caller_company or None
    else:
        # HR is hard-pinned to their own employer — query param is ignored.
        if not caller_company:
            raise HTTPException(
                status_code=403,
                detail="No company linked to this profile — correction analytics are tenant-scoped.",
            )
        scope_employer_id = caller_company

    rows: List[Dict[str, Any]] = weekly_corrections_by_reason(
        employer_id=scope_employer_id,
        weeks_back=weeks_back,
    )

    return {
        "employer_id": scope_employer_id,
        "weeks_back": weeks_back,
        "buckets": rows,
        "totals_by_reason": summarize_by_reason(rows),
        "total": sum(r["count"] for r in rows),
    }
