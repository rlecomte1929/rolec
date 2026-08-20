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

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)
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
    resolve_case_corridor,
)

log = logging.getLogger(__name__)

VALID_PERMIT_TYPES = {
    "eu_blue_card", "work_permit", "skilled_worker_visa", "eea_registration", "other"
}


class MilestoneCreate(BaseModel):
    milestone_type: str
    target_date: Optional[str] = None
    sort_order: Optional[int] = 0
    book_early_alert: Optional[str] = None


class MilestoneUpdate(BaseModel):
    status: Optional[str] = None
    completed_date: Optional[str] = None
    target_date: Optional[str] = None
    notes: Optional[str] = None
    evidence_url: Optional[str] = None


class ImmigrationCaseCreate(BaseModel):
    case_id: str
    corridor_from: str
    corridor_to: str
    permit_type: str
    partner_name: Optional[str] = None
    expected_submission_date: Optional[str] = None
    expected_grant_date: Optional[str] = None


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
        try:
            insert_audit_log(
                conn,
                entity_type="immigration_milestone",
                entity_id=milestone_id,
                action_type=ACTION_INSERT,
                actor_type=ACTOR_HUMAN,
                actor_id=hr_user.get("id"),
                new_value={"event": "milestone_created", "case_id": case_id,
                           "milestone_type": body.milestone_type},
            )
        except Exception:
            log.exception("audit: create_milestone case=%s", case_id)
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
        if result:
            try:
                insert_audit_log(
                    conn,
                    entity_type="immigration_milestone",
                    entity_id=milestone_id,
                    action_type=ACTION_UPDATE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=hr_user.get("id"),
                    new_value={"event": "milestone_updated", "fields": list(updates.keys())},
                )
            except Exception:
                log.exception("audit: update_milestone ms=%s", milestone_id)

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
    # I-3 Stage 3: match the interview's per-corridor question set so progress %
    # is computed against the same questions the employee is answering.
    questions = load_questions(corridor=resolve_case_corridor(case_id, current_user.get("org_id", "")))
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
        try:
            insert_audit_log(
                conn,
                entity_type="immigration_case",
                entity_id=imm_case_id,
                action_type=ACTION_INSERT,
                actor_type=ACTOR_HUMAN,
                actor_id=hr_user.get("id"),
                new_value={"event": "immigration_case_created", "case_id": body.case_id,
                           "permit_type": body.permit_type},
            )
        except Exception:
            log.exception("audit: create_immigration_case case=%s", body.case_id)

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

    # [AIQ-1881] immigration_cases.case_id holds the CANONICAL case id — all 4
    # production rows join on case_assignments.case_id and none on the assignment
    # id — but this route's path param may carry either form (the ownership check
    # directly above matches `id = :case_id OR case_id = :case_id`). Keying the
    # lookup on the raw path id therefore 404s an employee arriving from an
    # assignment-id URL even when their immigration case exists. Same failure as
    # AIQ-1704. Resolve once, then query on the resolved value.
    lookup_id = _canonical_case_id(case_id)

    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT * FROM public.immigration_cases
                WHERE case_id = :case_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"case_id": lookup_id},
        ).mappings().first()

    if row:
        result = _serialize_imm_case(row)
        result["state"] = "open"
        return result

    # [AIQ-1881] No immigration case. This used to 404 with "Contact your HR
    # team" — a dead end pointing at someone who had nothing to give: HR's own
    # available-forms and milestones come back empty for the same case, and
    # nothing in the product ever calls POST /api/hr/immigration/cases. Both
    # roles terminated with no next action.
    #
    # Return 200 with the honest state instead. Note we deliberately do NOT
    # create an immigration case implicitly: `permit_type` is mandatory and
    # validated against VALID_PERMIT_TYPES, and a free-movement national has no
    # permit to track. Auto-opening a permit file for someone who needs none
    # asserts a process that does not exist — the same class of error as
    # offering Ireland an EU Blue Card.
    return _absent_immigration_case_state(lookup_id)


# ---------------------------------------------------------------------------
# [AIQ-1881] Absent-immigration-case state
# ---------------------------------------------------------------------------

def _canonical_case_id(case_id: str) -> str:
    """Resolve any id form this route may carry to the canonical case id.

    Falls back to the argument when resolution fails: a best-effort resolver
    must never turn a readable page into an error.
    """
    try:
        ids = db.resolve_case_ids(case_id)
        if ids is not None and getattr(ids, "canonical_case_id", None):
            return str(ids.canonical_case_id)
    except Exception:  # noqa: BLE001 - resolution is best-effort
        log.exception("immigration: case-id resolution failed case=%s", case_id)
    return case_id


def _absent_immigration_case_state(case_id: str) -> Dict[str, Any]:
    """What to tell an employee who has no immigration case yet.

    Three honest answers, never a dead end:

    * ``no_permit_required`` — they hold free movement to this destination, so
      the absence of a permit file is the CORRECT and COMPLETE answer, not a
      gap. Saying "contact HR" to a Spanish national moving to Dublin invents a
      problem she does not have.
    * ``awaiting_hr`` — a permit really is needed and nobody has opened the
      file. Names who acts next instead of bouncing her to a person who, today,
      has no create action in the product either.
    * ``coverage_gap`` — we cannot categorise her (no nationality or no
      destination on the case). We say we do not know rather than guessing;
      an unknown nationality must never be silently treated as free movement.

    Nationality is categorised through ``nationality_class.classify`` — the
    single source of truth for "does this person have free movement?" — never by
    matching on country names, per the EEA permit-gating invariant.
    """
    from ..services.nationality_class import classify
    from ..services.relocation_plan_view_service import load_profile_draft_for_case
    from ..services.wizard_draft_mapper import extract_profile_from_wizard_draft
    from ..db import SessionLocal

    nationality: Optional[str] = None
    dest_country: Optional[str] = None

    try:
        with SessionLocal() as session:
            draft = load_profile_draft_for_case(session, case_id)
        nationality = (extract_profile_from_wizard_draft(draft or {}) or {}).get("nationality")
    except Exception:  # noqa: BLE001 - degrade to coverage_gap, never 500
        log.exception("immigration: nationality lookup failed case=%s", case_id)

    try:
        details = _get_case_details(case_id, "") or {}
        dest_country = details.get("dest_country")
    except Exception:  # noqa: BLE001
        log.exception("immigration: destination lookup failed case=%s", case_id)

    base: Dict[str, Any] = {
        "state": "coverage_gap",
        "immigration_case": None,
        "case_id": case_id,
        "nationality_class": None,
        "destination_country": dest_country,
    }

    if not nationality or not dest_country:
        missing = "your nationality" if not nationality else "your destination"
        base.update({
            "headline": "We need one more detail before we can confirm your immigration steps",
            "detail": (
                f"Your relocation case does not yet record {missing}, and that is the "
                "single field that decides whether you need a permit at all. We will not "
                "guess it."
            ),
            "next_action": "Complete your intake so we can confirm what applies to you.",
        })
        return base

    klass = classify(nationality, dest_country)
    base["nationality_class"] = klass

    if klass is None:
        # The classifier could not place this nationality — it returns None for
        # forms outside its lookup tables (e.g. "Venezuelan" today, though "VE"
        # and "Indian" both resolve). Saying "a permit is needed" would assert a
        # requirement we have not established, and "no permit needed" would be
        # far worse. Say we do not know.
        base.update({
            "headline": "We could not confirm what your nationality requires for this move",
            "detail": (
                "Your nationality is recorded but we cannot yet match it to an immigration "
                "route for this destination, so we are not going to guess. Your HR team can "
                "confirm your permit position."
            ),
            "next_action": "Ask your HR team to confirm your permit requirement.",
        })
        return base

    if klass in ("OWN_NATIONAL", "EU_EEA"):
        base.update({
            "state": "no_permit_required",
            "headline": "You do not need a work permit or visa for this move",
            "detail": (
                "You have freedom of movement to this destination, so there is no permit "
                "application to track and no immigration file to open. This is the complete "
                "answer, not a missing one — the rest of your setup is in your relocation plan."
            ),
            "next_action": None,
        })
        return base

    base.update({
        "state": "awaiting_hr",
        "headline": "Your immigration file has not been opened yet",
        "detail": (
            "This move needs a permit, and your HR team opens the file that tracks it. "
            "Nothing is required from you until they do — you will see your document "
            "checklist here as soon as it exists."
        ),
        "next_action": "Your HR team opens your immigration file. No action needed from you yet.",
    })
    return base


# ---------------------------------------------------------------------------
# Private DB helpers
# ---------------------------------------------------------------------------

