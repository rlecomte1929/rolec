"""Mobility graph case context API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...database import db
from ...services.case_context_service import CaseContextService, CaseContextError
from ...services.requirement_evaluation_service import RequirementEvaluationService
from ...services.next_action_service import NextActionService

router = APIRouter(prefix="/api/mobility", tags=["mobility"])


@router.get("/cases/{case_id}/context")
def get_mobility_case_context(case_id: str) -> dict:
    """
    Return normalized mobility graph context for ``case_id`` (UUID).

    Response keys: ``meta``, ``case``, ``people``, ``documents``,
    ``applicable_rules``, ``requirements``, ``evaluations``.
    """
    try:
        with db.engine.connect() as conn:
            ctx = CaseContextService().fetch(conn, case_id)
    except CaseContextError as e:
        raise HTTPException(
            status_code=503,
            detail={"code": e.code, "message": e.message},
        ) from e

    meta = ctx.get("meta") or {}
    if not meta.get("ok", True):
        raise HTTPException(status_code=400, detail=meta.get("error") or "Invalid request")
    if not meta.get("case_found"):
        raise HTTPException(status_code=404, detail="Mobility case not found")
    return ctx


@router.post("/cases/{case_id}/evaluate-requirements")
def evaluate_mobility_case_requirements(case_id: str) -> dict:
    """
    Run deterministic system evaluation for applicable policy rules, upsert
    ``case_requirement_evaluations`` (evaluated_by=system), return results + fresh context.
    """
    try:
        with db.engine.begin() as conn:
            ev = RequirementEvaluationService().evaluate_case(conn, case_id)
            err = ev.get("error")
            if err:
                code = (err.get("code") or "").strip()
                if code == "case_not_found":
                    raise HTTPException(status_code=404, detail=err.get("message") or "Mobility case not found")
                raise HTTPException(status_code=400, detail=err)
            ctx = CaseContextService().fetch(conn, case_id)
    except HTTPException:
        raise
    except CaseContextError as e:
        raise HTTPException(
            status_code=503,
            detail={"code": e.code, "message": e.message},
        ) from e

    return {
        "evaluation": {
            "evaluated_at": (ev.get("meta") or {}).get("evaluated_at"),
            "evaluated_by": (ev.get("meta") or {}).get("evaluated_by"),
            "evaluated_count": (ev.get("meta") or {}).get("evaluated_count", 0),
            "results": ev.get("results") or [],
        },
        "context": ctx,
    }


@router.get("/cases/{case_id}/next-actions")
def get_mobility_case_next_actions(case_id: str) -> dict:
    """
    User-facing next steps derived from open evaluations (missing / needs_review)
    plus optional household spouse reminder from case metadata.
    """
    with db.engine.connect() as conn:
        payload = NextActionService().list_actions(conn, case_id)

    meta = payload.get("meta") or {}
    if not meta.get("ok", True):
        err = meta.get("error") or {}
        if isinstance(err, dict) and err.get("code") == "mobility_schema_unavailable":
            raise HTTPException(status_code=503, detail=err)
        raise HTTPException(status_code=400, detail=err if err else "Invalid request")
    if not meta.get("case_found"):
        raise HTTPException(status_code=404, detail="Mobility case not found")
    return payload
