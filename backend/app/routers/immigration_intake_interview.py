"""
immigration_intake_interview.py — interview-flow routes.

Houses 2 endpoints:
  GET  /api/employee/cases/{case_id}/interview/next     (next question)
  POST /api/employee/cases/{case_id}/interview/answer   (submit answer)
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db
from ..services.immigration_interview_engine import (
    AddressGap,
    QuestionNode,
    compute_completion_pct,
    compute_section_progress,
    detect_address_gaps,
    get_next_question,
    get_section_summary,
    get_vault_updates,
    load_questions,
    validate_answer,
)
from ..services.immigration_service import (
    _apply_vault_updates,
    _check_consent,
    _load_or_create_session,
    _load_profile_for_case_employee,
    _load_session_for_update,
    _save_session,
)


class InterviewAnswerBody(BaseModel):
    question_id: str
    answer_value: Any
    skip: Optional[bool] = False

router = APIRouter(prefix="/api", tags=["immigration-intake-interview"])


@router.get("/employee/cases/{case_id}/interview/next")
def interview_next(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    IMM-06 — Return the next unanswered interview question.

    Creates a new interview session if none exists for this case+employee.
    Returns None as `next_question` when the interview is complete.
    """
    employee_id = current_user["id"]

    if not _check_consent(case_id, employee_id):
        raise HTTPException(status_code=403, detail="Consent required before starting interview.")

    session = _load_or_create_session(case_id, employee_id, current_user.get("org_id", ""))
    vault = _load_profile_for_case_employee(case_id, employee_id) or {}

    confirmed = list(session.get("prefilled_fields") or [])
    answers = dict(session.get("answers") or {})

    questions = load_questions()
    next_q = get_next_question(answers, vault, confirmed, questions)

    progress = compute_section_progress(answers, questions)
    completion = compute_completion_pct(answers, questions)

    return {
        "session_id": session["id"],
        "next_question": next_q,
        "completion_pct": completion,
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
        "is_complete": next_q is None,
    }


@router.post("/employee/cases/{case_id}/interview/answer")
def interview_answer(
    case_id: str,
    body: InterviewAnswerBody,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    IMM-06 — Submit an answer to an interview question.

    Validates the answer, saves to vault if the question maps to a vault field,
    updates session state, checks for address gaps, and returns the next question.

    Uses SELECT … FOR UPDATE to prevent concurrent corruption of session state.
    """
    employee_id = current_user["id"]

    if not _check_consent(case_id, employee_id):
        raise HTTPException(status_code=403, detail="Consent required before answering.")

    questions = load_questions()
    q_map = {q.id: q for q in questions}
    question = q_map.get(body.question_id)
    if not question:
        raise HTTPException(status_code=422, detail=f"Unknown question_id '{body.question_id}'.")

    # Validate answer (unless explicitly skipping)
    if not body.skip:
        validation = validate_answer(question, body.answer_value)
        if not validation.is_valid:
            raise HTTPException(status_code=422, detail=validation.error)

    answer_value = None if body.skip else body.answer_value

    # Load session with row-level lock to prevent concurrent updates
    session = _load_session_for_update(case_id, employee_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active interview session found. Call /next first.")

    answers: Dict[str, Any] = dict(session.get("answers") or {})
    confirmed_prefills: List[str] = list(session.get("prefilled_fields") or [])
    skipped: List[str] = list(session.get("skipped_fields") or [])

    # Record answer or skip
    if body.skip:
        if question.id not in skipped:
            skipped.append(question.id)
    else:
        answers[question.id] = answer_value
        # If this was a pre-filled question being confirmed, add to confirmed_prefills
        if question.vault_field and question.vault_field not in confirmed_prefills:
            vault_check = _load_profile_for_case_employee(case_id, employee_id) or {}
            if vault_check.get(question.vault_field):
                confirmed_prefills.append(question.vault_field)

    # Vault updates
    vault_updated: List[str] = []
    if not body.skip and question.vault_field:
        vault_updates = get_vault_updates(question, answer_value)
        if vault_updates:
            _apply_vault_updates(case_id, employee_id, vault_updates, current_user.get("org_id", ""))
            vault_updated = list(vault_updates.keys())

    # Address gap detection
    gap_warnings: List[Dict[str, Any]] = []
    if question.vault_field == "address_history" and not body.skip:
        try:
            addr_list = answer_value if isinstance(answer_value, list) else []
            gaps = detect_address_gaps(addr_list)
            gap_warnings = [
                {
                    "gap_days": g.gap_days,
                    "message": f"There is a {g.gap_days}-day gap in your address history between "
                               f"{g.from_address.get('to_date', '?')} and "
                               f"{g.to_address.get('from_date', '?')}. "
                               "Please add any addresses you lived at during this period.",
                }
                for g in gaps
            ]
        except Exception:
            pass

    # Recompute progress
    vault = _load_profile_for_case_employee(case_id, employee_id) or {}
    completion = compute_completion_pct(answers, questions)
    progress = compute_section_progress(answers, questions)
    next_q = get_next_question(answers, vault, confirmed_prefills, questions)

    # Determine completed sections
    completed_sections = [sid for sid, sp in progress.items() if sp.is_complete]
    completed_at_ts = _now_iso() if next_q is None else None

    # Persist session
    _save_session(
        session_id=session["id"],
        answers=answers,
        skipped_fields=skipped,
        prefilled_fields=confirmed_prefills,
        current_section=next_q["section"] if next_q else None,
        current_question_id=next_q["question_id"] if next_q else None,
        completed_sections=completed_sections,
        completion_pct=completion,
        completed_at=completed_at_ts,
    )

    # Log access
    logged_fields = vault_updated or [question.id]
    _log_access(
        case_id=case_id,
        profile_id=None,
        user_id=employee_id,
        role="employee",
        action="interview_answer",
        fields=logged_fields,
    )

    return {
        "session_id": session["id"],
        "question_answered": body.question_id,
        "vault_updated": vault_updated,
        "next_question": next_q,
        "completion_pct": completion,
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
        "gap_warnings": gap_warnings,
        "is_complete": next_q is None,
    }


