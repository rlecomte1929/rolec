"""Admin-only mobility case inspection (read-only)."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from ...database import db
from ...services.case_context_service import CaseContextError, CaseContextService
from ...services.mobility_inspect_service import fetch_audit_logs_for_mobility_case
from .admin import require_admin

router = APIRouter(prefix="/api/admin/mobility", tags=["admin-mobility"])


@router.get("/cases/{case_id}/inspect")
def inspect_mobility_case(case_id: str, _user: dict = Depends(require_admin)) -> Dict[str, Any]:
    """
    Full mobility context plus audit log entries scoped to this case (UUID).
    """
    try:
        with db.engine.connect() as conn:
            ctx = CaseContextService().fetch(conn, case_id)
            meta = ctx.get("meta") or {}
            if not meta.get("ok", True):
                raise HTTPException(status_code=400, detail=meta.get("error") or "Invalid case id")
            if not meta.get("case_found"):
                raise HTTPException(status_code=404, detail="Mobility case not found")
            audit_logs: List[Dict[str, Any]] = fetch_audit_logs_for_mobility_case(conn, case_id)
    except HTTPException:
        raise
    except CaseContextError as e:
        raise HTTPException(status_code=503, detail={"code": e.code, "message": e.message}) from e

    return {"context": ctx, "audit_logs": audit_logs}
