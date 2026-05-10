"""Mobility graph case context API."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ...database import db
from ...services.case_context_service import CaseContextService, CaseContextError
from ...services.mobility_route_access import enforce_mobility_graph_read_access
from ...services.next_action_service import NextActionService
from ...services.requirement_evaluation_service import RequirementEvaluationService

router = APIRouter(prefix="/api/mobility", tags=["mobility"])


async def mobility_authenticated_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Same as main.get_current_user; imported lazily to avoid circular imports at startup."""
    from backend.main import get_current_user as main_get_current_user  # noqa: WPS433

    return await main_get_current_user(request, authorization)


@router.get("/cases/{case_id}/context")
async def get_mobility_case_context(
    case_id: str,
    user: Dict[str, Any] = Depends(mobility_authenticated_user),
) -> dict:
    """
    Return normalized mobility graph context for ``case_id`` (UUID).

    Response keys: ``meta``, ``case``, ``people``, ``documents``,
    ``applicable_rules``, ``requirements``, ``evaluations``.
    """
    enforce_mobility_graph_read_access(db, case_id, user)
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


@router.post(
    "/cases/{case_id}/evaluate-requirements",
    deprecated=True,
    summary="Deprecated: use admin assignment-scoped evaluation",
)
async def evaluate_mobility_case_requirements(
    case_id: str,
    user: Dict[str, Any] = Depends(mobility_authenticated_user),
) -> dict:
    """
    **Deprecated.** Admin-only. Prefer
    ``POST /api/admin/mobility/assignments/{assignment_id}/evaluate-requirements``.

    Run deterministic system evaluation for applicable policy rules, upsert
    ``case_requirement_evaluations`` (evaluated_by=system), return results + fresh context.
    """
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail=(
                "Admin only. Use POST /api/admin/mobility/assignments/{assignment_id}/evaluate-requirements "
                "with a linked assignment."
            ),
        )
    enforce_mobility_graph_read_access(db, case_id, user)
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
async def get_mobility_case_next_actions(
    case_id: str,
    user: Dict[str, Any] = Depends(mobility_authenticated_user),
) -> dict:
    """
    User-facing next steps derived from open evaluations (missing / needs_review)
    plus optional household spouse reminder from case metadata.
    """
    enforce_mobility_graph_read_access(db, case_id, user)
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
