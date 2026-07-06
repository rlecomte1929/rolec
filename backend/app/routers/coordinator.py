"""AIQ-1414 Phase 3 — Mobility Coordinator HTTP endpoint.

Exposes the (flag-gated) persistent coordinator to **HR of the case's company** or the
**assigned employee**, for one relocation case. When ``RELOPASS_AI_COORDINATOR_ENABLED``
is OFF (the default) the route 404s, so the whole feature is inert in production until it
is enabled behind the human gate (Phase 5). PII masking + per-session cost telemetry are
handled inside ``coordinator_agent.respond``.

Dual-registered in ``backend/app/main.py`` AND ``backend/main.py`` per CLAUDE.md — a router
registered only in the modular app 405s in prod.

NB: no ``from __future__ import annotations`` here — slowapi's ``@limiter.limit`` wrapper
re-resolves the handler's forward-ref annotations against its own globals, which raises
PydanticUndefinedAnnotation on the Pydantic body when the future import is present.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ...rate_limit import limiter
from ..auth_deps import require_case_access, require_hr_or_employee
from ..services import coordinator_agent
from ..services import coordinator_session_store as store
from ..services.coordinator_context_builder import coordinator_enabled

router = APIRouter(tags=["coordinator"])


class RespondBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class RespondResponse(BaseModel):
    answer: str
    model: str
    case_id: str


@router.post("/api/cases/{case_id}/coordinator/respond", response_model=RespondResponse)
@limiter.limit("15/minute;150/hour")
def coordinator_respond(
    case_id: str,
    body: RespondBody,
    request: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """Send one message to the case's Mobility Coordinator and return its reply.

    Flag-gated (404 when OFF). Access is the assigned employee, or HR/Admin of the case's
    company — enforced by ``require_case_access`` (404 unknown case / 403 not authorized).
    Rate-limited (slowapi) to bound cost/abuse on the live LLM endpoint.
    """
    if not coordinator_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    assignment = require_case_access(case_id, user)
    employee_id = assignment.get("employee_user_id") if isinstance(assignment, dict) else None

    result = coordinator_agent.respond(case_id, body.message, employee_id=employee_id)
    if result is None:  # flag flipped between the gate check and the call
        raise HTTPException(status_code=404, detail="Not found")
    return result


class SessionResponse(BaseModel):
    case_id: str
    rolling_summary: str
    recent_turns: List[Dict[str, Any]]
    model: str
    status: str


@router.get("/api/cases/{case_id}/coordinator/session", response_model=SessionResponse)
def coordinator_session(
    case_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """Load the case's persisted coordinator session (rolling summary + recent turns) so the
    UI can render the thread. Read-only, no side effects. Flag-gated (404 when OFF); access
    via ``require_case_access``. Returns an empty session when none exists yet."""
    if not coordinator_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    require_case_access(case_id, user)
    session = store.get(str(case_id))
    if session is None:
        return {"case_id": str(case_id), "rolling_summary": "", "recent_turns": [],
                "model": "", "status": "none"}
    return {
        "case_id": str(case_id),
        "rolling_summary": session.get("rolling_summary") or "",
        "recent_turns": session.get("recent_turns") or [],
        "model": session.get("model") or "",
        "status": session.get("status") or "active",
    }
