"""Test-Drive QA staged provisioning harness.

POST /api/test-drive/qa/provision-stage — provisions a test-drive session and
walks it to a named stage of the real journey, so QA can start at any point
without clicking through the full ~50-step flow by hand:

  * ``credentials``     — the real ``/api/test-drive/provision`` path only
                          (HR + Employee identities, company, seeded policy,
                          ``test_sessions`` row).
  * ``case_created``    — + HR creates and assigns a case, exactly as the HR UI
                          does (``create_case`` + ``assign_case`` in
                          ``backend/main.py``).
  * ``intake_complete`` — + the employee wizard draft is written through
                          ``PATCH /api/cases/{id}`` (``cases_write.patch_case``,
                          corridor lock included) and submitted through
                          ``POST /api/employee/assignments/{id}/submit``
                          (``submit_assignment`` — the same call that kicks off
                          the background relocation-plan build).
  * ``roadmap_ready``   — + waits (bounded) for that background build to land
                          its ``case_milestones``, i.e. the employee plan view
                          is populated.

REUSES THE REAL CODE PATHS. Every stage calls the same handler/service
functions the live journey runs — no direct row inserts — so a session
provisioned here is indistinguishable from one a tester walked manually, and a
regression in any stage of the real journey surfaces here too.

Gating (hard requirements — this must be unreachable for real campaigns):
  1. 404 unless ``RELOPASS_TEST_DRIVE_ENABLED`` is truthy (same dark-ship gate
     as the public test-drive surface).
  2. 403 unless the request's ``campaign`` matches ``qa-*``. The campaign is
     REQUIRED and never falls back to ``RELOPASS_TEST_DRIVE_CAMPAIGN`` — so
     ``insead-2026`` (or any real company campaign) can never reach this
     endpoint, even where the flag is on.

No migrations: everything here writes through existing code paths into
existing tables (``test_sessions`` et al. from the TD-1 migration).
"""
# NB: no `from __future__ import annotations` — mirrors test_drive.py (slowapi
# resolves handler annotations against module globals).
import logging
import re
import time
from datetime import date, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from starlette.responses import Response as StarletteResponse

from ...database import db
from ..services.test_drive_corridor import LOCKED_CORRIDORS, TEST_DRIVE_CORRIDOR_ROUTES
from .test_drive import ProvisionRequest, _emit_funnel_event, _test_drive_enabled, provision

router = APIRouter(prefix="/api/test-drive", tags=["test-drive-qa"])
logger = logging.getLogger(__name__)

# Journey order matters: each stage implies all the ones before it.
STAGES = ("credentials", "case_created", "intake_complete", "roadmap_ready")

# The ONLY campaigns this harness will provision. Anchored + full-match so a
# real campaign can't smuggle through as a prefix/suffix (e.g. "insead-qa-x").
_QA_CAMPAIGN_RE = re.compile(r"^qa-[A-Za-z0-9][A-Za-z0-9_-]{0,58}$")


class StageProvisionRequest(BaseModel):
    stage: str = Field(...)
    # REQUIRED (unlike /provision) and validated against qa-* — see module docstring.
    campaign: str = Field(..., min_length=1, max_length=64)
    first_name: str = Field("QA", min_length=1, max_length=40)
    corridor_id: Optional[str] = Field(None, max_length=64)
    invite_token: Optional[str] = Field(None, max_length=200)
    # roadmap_ready only: how long to wait for the background plan build.
    roadmap_timeout_seconds: int = Field(60, ge=1, le=120)

    @field_validator("stage")
    @classmethod
    def _valid_stage(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in STAGES:
            raise ValueError(f"stage must be one of {list(STAGES)}")
        return s

    @field_validator("campaign")
    @classmethod
    def _qa_campaign_only(cls, v: str) -> str:
        # Shape-validated here (422); the authorization decision (403) is in the
        # handler so a wrong campaign is an explicit rejection, not a schema error.
        return (v or "").strip()


def _require_qa_campaign(campaign: str) -> str:
    """403 unless the campaign matches qa-*. This is the second hard gate: the
    harness must be unreachable for ``insead-2026`` or any real company campaign."""
    if not _QA_CAMPAIGN_RE.match(campaign):
        raise HTTPException(
            status_code=403,
            detail="QA staged provisioning is restricted to qa-* campaigns.",
        )
    return campaign


def _load_journey_user(username: str, label: str) -> Dict[str, Any]:
    """The user dict the auth dependency would hand the real handlers.

    ``get_current_user`` resolves a token to the ``users`` row; the harness
    resolves the just-provisioned username to the same row, so downstream
    handlers see an identical shape. ``is_admin`` mirrors the dependency's
    explicit default for non-admins."""
    user = db.get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=502,
            detail=f"Provisioned {label} account {username!r} not found after provision.",
        )
    user = dict(user)
    user.setdefault("is_admin", False)
    return user


def _build_intake_draft(
    corridor_id: str, first_name: str, emp_email: str, company_name: Optional[str]
) -> Dict[str, Any]:
    """A complete CaseDraftDTO payload for the locked corridor — the same shape
    the employee wizard PATCHes. Fills every required step-1 basic (see
    ``intake_completeness.REQUIRED_INTAKE_BASICS``) plus profile/assignment
    context so submit's completeness gate passes. patch_case re-stamps the
    route via the corridor lock; we send the locked route to begin with."""
    route = TEST_DRIVE_CORRIDOR_ROUTES[corridor_id]
    today = date.today()
    return {
        "relocationBasics": {
            "originCountry": route["home_country"],
            "originCity": route["home_city"],
            "destCountry": route["host_country"],
            "destCity": route["host_city"],
            "purpose": "work",
            "targetMoveDate": (today + timedelta(days=90)).isoformat(),
            "durationMonths": 24,
            "hasDependents": False,
        },
        "employeeProfile": {
            "fullName": f"{first_name} QA Tester",
            "nationality": route["home_country"],
            "passportCountry": route["home_country"],
            "passportExpiry": (today + timedelta(days=6 * 365)).isoformat(),
            "residenceCountry": route["home_country"],
            "email": emp_email,
        },
        "familyMembers": {"maritalStatus": "solo", "children": []},
        "assignmentContext": {
            "employerName": company_name or f"Test Drive {first_name}",
            "employerCountry": route["host_country"],
            "workLocation": route["host_city"],
            "contractStartDate": (today + timedelta(days=104)).isoformat(),
            "contractType": "permanent",
            "salaryBand": "L4",
            "jobTitle": "QA Engineer",
            "seniorityBand": "senior",
        },
        "services": ["housing", "immigration", "moving"],
    }


def _stage_case_created(
    request: Request, hr_user: Dict[str, Any], emp_email: str, first_name: str
) -> "tuple[str, str]":
    """HR creates + assigns a case via the REAL monolith handlers. Returns
    (case_id, assignment_id). Imported lazily: backend.main imports this
    module's package, so a top-level import would be circular."""
    from ... import main as monolith  # noqa: PLC0415 — circular at module load
    from ...schemas import AssignCaseRequest  # noqa: PLC0415

    created = monolith.create_case(user=hr_user)
    case_id = created.caseId

    assign_body = AssignCaseRequest(
        employeeIdentifier=emp_email,
        employeeFirstName=first_name,
        employeeLastName="Test-Drive",
    )
    assigned = monolith.assign_case(case_id, assign_body, request, user=hr_user)
    if isinstance(assigned, StarletteResponse):
        # assign_case converts unexpected failures into a JSONResponse(500);
        # surface that as an explicit harness failure instead of returning it.
        raise HTTPException(status_code=502, detail="Case assignment failed during staged provisioning.")
    return case_id, assigned.assignmentId


def _stage_intake_complete(
    case_id: str,
    assignment_id: str,
    emp_user: Dict[str, Any],
    draft: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    """Employee fills the wizard + submits — the REAL intake path. patch_case
    applies the corridor lock and fires the same deferred side effects (via the
    caller's BackgroundTasks); submit_assignment runs the full completeness
    gate and enqueues the background relocation-plan build."""
    from ... import main as monolith  # noqa: PLC0415 — circular at module load
    from .. import schemas as app_schemas  # noqa: PLC0415
    from .cases_write import patch_case  # noqa: PLC0415

    patch = app_schemas.CaseDraftDTO.model_validate(draft)
    patch_case(case_id, patch, background_tasks, user=emp_user)
    monolith.submit_assignment(assignment_id, user=emp_user)


def _wait_for_roadmap(case_id: str, timeout_seconds: int) -> "tuple[bool, int]":
    """Poll (read-only) for the case_milestones the background plan build
    writes after submit — the artifact the employee plan view renders. Returns
    (ready, milestone_count). Bounded: on timeout the caller reports the stage
    honestly rather than failing the whole provision."""
    deadline = time.monotonic() + timeout_seconds
    count = 0
    while True:
        try:
            count = len(db.list_case_milestones(case_id) or [])
        except Exception:  # noqa: BLE001 — a transient read error must not abort the wait
            logger.warning("qa provision-stage: milestone poll failed case=%s", case_id, exc_info=True)
            count = 0
        if count > 0:
            return True, count
        if time.monotonic() >= deadline:
            return False, count
        time.sleep(2)


@router.post("/qa/provision-stage")
def provision_stage(
    body: StageProvisionRequest, request: Request, background_tasks: BackgroundTasks
):
    """Provision a test-drive session directly to ``body.stage``.

    Gates: 404 when RELOPASS_TEST_DRIVE_ENABLED is off; 403 unless the
    campaign matches qa-*. Rate limiting rides on the inner /provision call
    (same slowapi bucket as the public surface).
    """
    # Gate 1 — same dark-ship flag as the whole test-drive surface.
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    # Gate 2 — qa-* campaigns only; never falls back to the env default.
    campaign = _require_qa_campaign(body.campaign)

    target = STAGES.index(body.stage)
    first_name = body.first_name.strip() or "QA"

    # ── Stage 1: credentials — the REAL /provision handler ───────────────────
    provisioned = provision(
        body=ProvisionRequest(
            first_name=first_name,
            corridor_id=body.corridor_id,
            invite_token=body.invite_token,
            campaign=campaign,
        ),
        request=request,
    )
    session_id = provisioned["session_id"]
    corridor_id = provisioned["corridor_id"]
    if corridor_id not in LOCKED_CORRIDORS:  # defensive; provision whitelists already
        raise HTTPException(status_code=502, detail=f"Unexpected corridor {corridor_id!r}.")

    result: Dict[str, Any] = {
        "ok": True,
        "stage": body.stage,
        "stage_reached": "credentials",
        "session_id": session_id,
        "campaign": campaign,
        "corridor_id": corridor_id,
        "hr": provisioned["hr"],
        "employee": provisioned["employee"],
        "case_id": None,
        "assignment_id": None,
        "roadmap_ready": False,
        "milestone_count": 0,
    }
    if target == 0:
        return result

    # ── Stage 2: case_created — HR create + assign (monolith handlers) ────────
    hr_user = _load_journey_user(provisioned["hr"]["username"], "HR")
    emp_user = _load_journey_user(provisioned["employee"]["username"], "employee")
    case_id, assignment_id = _stage_case_created(
        request, hr_user, provisioned["employee"]["email"], first_name
    )
    result.update(case_id=case_id, assignment_id=assignment_id, stage_reached="case_created")
    _emit_funnel_event(
        event_type="hr-handoff", session_id=session_id, campaign=campaign,
        corridor_id=corridor_id, metadata={"via": "qa-harness"},
    )
    if target == 1:
        return result

    # ── Stage 3: intake_complete — employee wizard PATCH + submit ────────────
    company_name = None
    company_id = db.get_hr_company_id(str(hr_user.get("id")))
    if company_id:
        company_name = (db.get_company(company_id) or {}).get("name")
    draft = _build_intake_draft(
        corridor_id, first_name, provisioned["employee"]["email"], company_name
    )
    _emit_funnel_event(
        event_type="intake-start", session_id=session_id, campaign=campaign,
        corridor_id=corridor_id, metadata={"via": "qa-harness"},
    )
    _stage_intake_complete(case_id, assignment_id, emp_user, draft, background_tasks)
    result["stage_reached"] = "intake_complete"
    _emit_funnel_event(
        event_type="intake-completed", session_id=session_id, campaign=campaign,
        corridor_id=corridor_id, metadata={"via": "qa-harness"},
    )
    if target == 2:
        return result

    # ── Stage 4: roadmap_ready — wait for the background plan build ──────────
    ready, milestone_count = _wait_for_roadmap(case_id, body.roadmap_timeout_seconds)
    result.update(roadmap_ready=ready, milestone_count=milestone_count)
    if ready:
        result["stage_reached"] = "roadmap_ready"
        _emit_funnel_event(
            event_type="roadmap-reached", session_id=session_id, campaign=campaign,
            corridor_id=corridor_id, metadata={"via": "qa-harness"},
        )
    else:
        # Honest partial: intake is submitted and the build is enqueued, but it
        # didn't land within the window. QA can poll the plan view or retry.
        result["ok"] = False
        result["note"] = (
            f"Background roadmap build did not complete within "
            f"{body.roadmap_timeout_seconds}s; session is at intake_complete."
        )

    logger.info(
        "qa provision-stage session=%s campaign=%s corridor=%s stage=%s reached=%s case=%s",
        session_id, campaign, corridor_id, body.stage, result["stage_reached"], case_id,
    )
    return result
