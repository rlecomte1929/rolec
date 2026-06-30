"""
Admin GDPR/DSAR desk (admin-only): a cross-tenant list of erasure requests. The
data-subject *actions* (export / erase) already exist as admin-authorized endpoints
(`GET /api/users/{id}/data-export`, `DELETE /api/users/{id}/data`) — this only adds
the missing cross-tenant registry so an admin can see every request in one pane.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..auth_deps import require_admin
from ...database import db

router = APIRouter(prefix="/api/admin", tags=["admin-dsar"])


def _missing_table(exc: Exception) -> bool:
    blob = str(getattr(exc, "orig", exc)).lower()
    return "42p01" in blob or "does not exist" in blob or "no such table" in blob


@router.get("/erasure-requests")
def list_erasure_requests(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    where = ""
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if status and status not in ("all", ""):
        where = " WHERE status = :status"
        params["status"] = status
    try:
        with db.engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT count(*) AS n FROM public.erasure_requests{where}"), params
            ).scalar() or 0
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, case_id, employee_id, org_id, status, reason,
                           requested_at, statutory_due_at, reviewed_by, reviewed_at, completed_at
                    FROM public.erasure_requests{where}
                    ORDER BY requested_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).mappings().all()
    except (ProgrammingError, OperationalError) as exc:
        if _missing_table(exc):
            return {"items": [], "total": 0, "limit": limit, "offset": offset, "table_ready": False}
        raise
    return {"items": [dict(r) for r in rows], "total": int(total), "limit": limit, "offset": offset, "table_ready": True}
