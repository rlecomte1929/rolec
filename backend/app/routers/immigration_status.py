"""
immigration_status.py — milestone, interview-status, and immigration-case
CRUD routes extracted from immigration.py (AUDIT-B9-imm-4).

Houses 8 endpoints:
  GET   /api/hr/cases/{case_id}/immigration/milestones
  POST  /api/hr/cases/{case_id}/immigration/milestones
  PATCH /api/hr/cases/{case_id}/immigration/milestones/{milestone_id}
  GET   /api/hr/cases/{case_id}/immigration/interview-status
  GET   /api/employee/cases/{case_id}/interview/status
  POST  /api/hr/immigration/cases                                (immigration-case shell)
  GET   /api/hr/immigration/cases/{immigration_case_id}
  GET   /api/employee/cases/{case_id}/immigration

WIRED (AUDIT-B9-imm-6): this router is registered in both backend/main.py and
backend/app/main.py and is the canonical handler for these routes. The original
immigration.py router is retained but no longer wired.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.immigration_interview_engine import (
    compute_completion_pct,
    compute_section_progress,
    get_section_summary,
    load_questions,
)
from ..services.immigration_service import (
    _check_consent,
    _get_case_details,
    _load_session,
    _log_access,
    _now_iso,
    _serialize_imm_case,
    _ts,
)

# Pydantic models — imported from immigration.py until imm-6 relocates them.
from .immigration import (
    ImmigrationCaseCreate,
    MilestoneCreate,
    MilestoneUpdate,
)

router = APIRouter(prefix="/api", tags=["immigration-status"])


@router.get("/hr/cases/{case_id}/immigration/milestones")
def list_milestones(
    case_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    with db.engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT id, milestone_type, status, sort_order, target_date,
                       completed_date, notes, evidence_url, book_early_alert,
                       created_at, updated_at
                FROM public.immigration_milestones
                WHERE case_id = :case_id
                ORDER BY sort_order ASC, created_at ASC
            """),
            {"case_id": case_id},
        ).mappings().all()
    milestones = []
    for r in rows:
        row = dict(r)
        for col in ("target_date", "completed_date", "created_at", "updated_at"):
            v = row.get(col)
            if hasattr(v, "isoformat"):
                row[col] = v.isoformat()
        milestones.append(row)
    return {"milestones": milestones}


@router.post("/hr/cases/{case_id}/immigration/milestones", status_code=status.HTTP_201_CREATED)
def create_milestone(
    case_id: str,
    body: MilestoneCreate,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    milestone_id = str(uuid.uuid4())
    now = _now_iso()
    with db.engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO public.immigration_milestones
                    (id, case_id, org_id, milestone_type, status, sort_order,
                     target_date, book_early_alert, created_at, updated_at)
                VALUES
                    (:id, :case_id, :org_id, :milestone_type, 'pending', :sort_order,
                     :target_date, :book_early_alert, :now, :now)
            """),
            {
                "id": milestone_id,
                "case_id": case_id,
                "org_id": org_id,
                "milestone_type": body.milestone_type,
                "sort_order": body.sort_order or 0,
                "target_date": body.target_date,
                "book_early_alert": body.book_early_alert,
                "now": now,
            },
        )
    return {"id": milestone_id, "milestone_type": body.milestone_type, "status": "pending"}


@router.patch("/hr/cases/{case_id}/immigration/milestones/{milestone_id}")
def update_milestone(
    case_id: str,
    milestone_id: str,
    body: MilestoneUpdate,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update.")

    valid_statuses = {"pending", "in_progress", "completed", "blocked", "not_applicable"}
    if "status" in updates and updates["status"] not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status '{updates['status']}'.")

    now = _now_iso()
    set_clauses = [f"{k} = :{k}" for k in updates]
    set_clauses.append("updated_at = :now")
    params = {"milestone_id": milestone_id, "case_id": case_id, "now": now, **updates}

    with db.engine.begin() as conn:
        result = conn.execute(
            text(f"""
                UPDATE public.immigration_milestones
                SET {', '.join(set_clauses)}
                WHERE id = :milestone_id AND case_id = :case_id
                RETURNING id, status, updated_at
            """),
            params,
        ).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    return dict(result)


# ---------------------------------------------------------------------------
# HR: GET /api/hr/cases/{case_id}/immigration/interview-status  (IMM-13)
# ---------------------------------------------------------------------------

@router.get("/hr/cases/{case_id}/immigration/interview-status")
def get_interview_status_hr(
    case_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    HR-facing view of the employee's immigration interview progress.
    Returns the stored completion_pct and session metadata without exposing
    any individual question answers (those stay employee-private).
    """
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT completion_pct, completed_at, started_at, last_active_at
                FROM public.interview_sessions
                WHERE case_id = :case_id
                ORDER BY started_at DESC
                LIMIT 1
            """),
            {"case_id": case_id},
        ).mappings().first()

    if not row:
        return {
            "has_session": False,
            "completion_pct": 0,
            "is_complete": False,
            "started_at": None,
            "last_active_at": None,
            "completed_at": None,
        }

    return {
        "has_session": True,
        "completion_pct": float(row["completion_pct"] or 0),
        "is_complete": row["completed_at"] is not None,
        "started_at": _ts(row["started_at"]),
        "last_active_at": _ts(row["last_active_at"]),
        "completed_at": _ts(row["completed_at"]),
    }


# ---------------------------------------------------------------------------
# Stubs for future tasks (return 501 with helpful message)
# ---------------------------------------------------------------------------


@router.get("/employee/cases/{case_id}/interview/status")
def interview_status(
    case_id: str,
    section_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    IMM-06 — Overall interview progress.

    If `section_id` query param is provided, returns detailed per-question
    breakdown for that section.
    """
    # Canonical UUID (AUTH-ID-1): consent_records / interview_sessions key on a
    # uuid employee_id. A legacy text id would never match (and used to risk a
    # uuid-cast error); the resolved auth_uuid binds correctly or is None → no
    # match (consent screen), never a 500.
    employee_id = current_user.get("auth_uuid")

    if not _check_consent(case_id, employee_id):
        raise HTTPException(status_code=403, detail="Consent required.")

    session = _load_session(case_id, employee_id)
    if not session:
        return {
            "has_session": False,
            "completion_pct": 0,
            "is_complete": False,
            "section_progress": {},
        }

    answers = dict(session.get("answers") or {})
    questions = load_questions()
    progress = compute_section_progress(answers, questions)
    completion = compute_completion_pct(answers, questions)

    result: Dict[str, Any] = {
        "has_session": True,
        "session_id": session["id"],
        "completion_pct": completion,
        "is_complete": session.get("completed_at") is not None,
        "started_at": _ts(session.get("started_at")),
        "last_active_at": _ts(session.get("last_active_at")),
        "completed_at": _ts(session.get("completed_at")),
        "section_progress": {
            sid: {
                "total_applicable": sp.total_applicable,
                "answered": sp.answered,
                "required_answered": sp.required_answered,
                "required_total": sp.required_total,
                "is_complete": sp.is_complete,
            }
            for sid, sp in progress.items()
        },
    }

    if section_id:
        result["section_detail"] = get_section_summary(section_id, answers, questions)

    return result



@router.post("/hr/immigration/cases", status_code=status.HTTP_201_CREATED)
def create_immigration_case(
    body: ImmigrationCaseCreate,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    MVG-6A — HR creates a permit tracking record for an existing relocation case.

    Validates permit_type, inserts into immigration_cases, and returns the new record.
    Returns 409 if an immigration case for this case_id already exists.
    """
    if body.permit_type not in VALID_PERMIT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid permit_type '{body.permit_type}'. "
                   f"Allowed: {', '.join(sorted(VALID_PERMIT_TYPES))}.",
        )

    # Prevent duplicates — one active immigration case per relocation case
    with db.engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM public.immigration_cases WHERE case_id = :case_id LIMIT 1"),
            {"case_id": body.case_id},
        ).mappings().first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An immigration case already exists for case_id '{body.case_id}'. "
                   f"Immigration case id: {existing['id']}",
        )

    imm_case_id = str(uuid.uuid4())
    now = _now_iso()

    with db.engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO public.immigration_cases
                    (id, case_id, corridor_from, corridor_to, permit_type,
                     partner_name, expected_submission_date, expected_grant_date,
                     status, document_statuses, created_by_hr_id, created_at, updated_at)
                VALUES
                    (:id, :case_id, :corridor_from, :corridor_to, :permit_type,
                     :partner_name, :expected_submission_date, :expected_grant_date,
                     'initiated', '{}', :created_by_hr_id, :now, :now)
            """),
            {
                "id": imm_case_id,
                "case_id": body.case_id,
                "corridor_from": body.corridor_from,
                "corridor_to": body.corridor_to,
                "permit_type": body.permit_type,
                "partner_name": body.partner_name,
                "expected_submission_date": body.expected_submission_date,
                "expected_grant_date": body.expected_grant_date,
                "created_by_hr_id": hr_user.get("id"),
                "now": now,
            },
        )

    # Fetch and return the full record
    with db.engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM public.immigration_cases WHERE id = :id"),
            {"id": imm_case_id},
        ).mappings().first()

    log.info("Immigration case created: %s for case_id %s by HR %s",
             imm_case_id, body.case_id, hr_user.get("id"))
    return _serialize_imm_case(row)


@router.get("/hr/immigration/cases/{immigration_case_id}")
def get_immigration_case_hr(
    immigration_case_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    MVG-6A/6C — HR fetches an immigration case by its own ID.

    Returns the full record including status, dates, and corridor.
    """
    with db.engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM public.immigration_cases WHERE id = :id"),
            {"id": immigration_case_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Immigration case not found.")

    return _serialize_imm_case(row)


@router.get("/employee/cases/{case_id}/immigration")
def get_immigration_case_employee(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    MVG-6B — Employee fetches the immigration case for their relocation case.

    Verifies the authenticated employee owns the given relocation case before
    returning the record.  Returns 404 if no immigration case exists yet
    (HR has not opened one), so the employee checklist page can show a friendly
    "contact HR" message.
    """
    user_role = (current_user.get("role") or current_user.get("user_role") or "").upper()
    is_hr_or_admin = user_role in ("HR", "ADMIN")

    if not is_hr_or_admin:
        # Employees must own the relocation case. Bind the canonical UUID
        # (AUTH-ID-1): case_assignments.employee_user_id is uuid-typed, so a
        # legacy text id would 500 here (this path has no DataError guard).
        # auth_uuid is a real UUID or None → no match → clean 403.
        employee_id = current_user.get("auth_uuid")
        with db.engine.begin() as conn:
            assignment = conn.execute(
                text("""
                    SELECT id FROM public.case_assignments
                    WHERE (id = :case_id OR case_id = :case_id)
                      AND employee_user_id = :employee_id
                    LIMIT 1
                """),
                {"case_id": case_id, "employee_id": employee_id},
            ).mappings().first()

        if not assignment:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this relocation case.",
            )
    # HR/Admin: skip ownership check — they can view any case's checklist

    # Look up immigration case by relocation case_id
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT * FROM public.immigration_cases
                WHERE case_id = :case_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"case_id": case_id},
        ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="No immigration case found for this relocation. Contact your HR team.",
        )

    return _serialize_imm_case(row)


# ---------------------------------------------------------------------------
# Private DB helpers
# ---------------------------------------------------------------------------

