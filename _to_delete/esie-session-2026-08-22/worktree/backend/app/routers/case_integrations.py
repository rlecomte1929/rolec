"""I-4 — case plan delivery endpoints (email this plan + calendar .ics).

  POST /api/cases/{case_id}/roadmap/email   email the case's plan (Resend)
  GET  /api/cases/{case_id}/calendar.ics    download the case's deadlines as .ics

Both are scoped via require_case_access (the case's employee, or same-company HR,
or admin). No MCP at runtime: email goes through the existing transactional
sender and the calendar is a generated, importable .ics.

WIRED (CLAUDE.md hard gate): registered in BOTH backend/main.py and
backend/app/main.py.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel

from ..auth_deps import get_current_user, require_case_access
from ..services.integrations import case_plan_delivery as delivery

router = APIRouter(prefix="/api/cases", tags=["case-integrations"])
log = logging.getLogger(__name__)


class EmailPlanBody(BaseModel):
    to: Optional[str] = None  # defaults to the caller's own email


@router.post("/{case_id}/roadmap/email")
def email_case_roadmap(
    case_id: str,
    body: EmailPlanBody = Body(default_factory=EmailPlanBody),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Email the case's relocation plan. 404 if the caller can't access the case."""
    require_case_access(case_id, user)
    to = (body.to or user.get("email") or "").strip()
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="No valid recipient email available.")
    try:
        return delivery.email_case_plan(case_id, to)
    except Exception as exc:  # noqa: BLE001 — send/render failure → 502
        log.error("email_case_plan failed case_id=%s: %s", case_id, exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Could not send the plan email. Please retry.")


@router.get("/{case_id}/calendar.ics")
def case_calendar_ics(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Return the case's milestones as a downloadable .ics (caller's timezone)."""
    require_case_access(case_id, user)
    # auth_uuid maps to profiles.id (the timezone source); falls back to UTC.
    ics = delivery.build_case_ics(case_id, user_id=user.get("auth_uuid") or user.get("id"))
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="relopass-case-{case_id}.ics"'
        },
    )
