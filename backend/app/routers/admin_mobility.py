"""Admin-only mobility case inspection (read-only)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from ...database import db
from ...services.admin_assignment_evaluation_trigger import run_evaluation_for_assignment
from ...services.case_context_service import CaseContextError, CaseContextService
from ...services.mobility_inspect_service import (
    build_mobility_operational_inspect,
    fetch_audit_logs_for_mobility_case,
)
from .admin import require_admin

log = logging.getLogger(__name__)

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
            operational = build_mobility_operational_inspect(conn, case_id, ctx)
            audit_logs: List[Dict[str, Any]] = fetch_audit_logs_for_mobility_case(conn, case_id)
    except HTTPException:
        raise
    except CaseContextError as e:
        raise HTTPException(status_code=503, detail={"code": e.code, "message": e.message}) from e

    return {"context": ctx, "audit_logs": audit_logs, "operational": operational}


@router.post("/assignments/{assignment_id}/evaluate-requirements")
def admin_evaluate_assignment_requirements(
    assignment_id: str,
    _user: dict = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Controlled run: resolve mobility_cases.id from assignment_mobility_links, execute
    RequirementEvaluationService (writes case_requirement_evaluations), return summary +
    next_actions preview. Not invoked from employee case-details or evidence upload.
    """
    out = run_evaluation_for_assignment(db, assignment_id)
    if not out.get("ok"):
        err = out.get("error") or {}
        code = (err.get("code") or "").strip()
        if code == "no_mobility_link":
            raise HTTPException(status_code=404, detail=err)
        if code in ("invalid_assignment_id",):
            raise HTTPException(status_code=400, detail=err)
        if code == "case_not_found":
            raise HTTPException(status_code=404, detail=err)
        if code == "schema_unavailable":
            raise HTTPException(status_code=503, detail=err)
        raise HTTPException(status_code=400, detail=err)
    # Strip internal flag for HTTP body
    body = {k: v for k, v in out.items() if k != "ok"}
    log.info(
        "admin_evaluate_assignment_requirements assignment_id=%s mobility_case_id=%s evaluated_count=%s",
        body.get("assignment_id"),
        body.get("mobility_case_id"),
        body.get("evaluated_count"),
    )
    return body
