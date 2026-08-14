"""
immigration_gdpr.py — GDPR subject-rights routes extracted from immigration.py
(AUDIT-B9-imm-5), implemented under IMM-17.

Houses 4 endpoints:
  GET  /api/employee/cases/{case_id}/my-data/export                  (IMM-17, Art. 15)
  POST /api/employee/cases/{case_id}/my-data/erasure-request         (IMM-17, files Art. 17 request)
  GET  /api/hr/immigration/erasure-requests                          (IMM-18, HR review queue)
  POST /api/hr/cases/{case_id}/immigration/process-erasure-request   (IMM-18, HR approve/reject)

The employee files an erasure request (IMM-17); HR/admin reviews it and, on approval,
the profile is anonymised in place via fn_anonymise_imm_profile (IMM-18).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from ..services.gdpr_export_service import build_data_export_pdf
from ..services.immigration_service import (
    PassportDecryption,
    _load_profile_for_case_employee,
    _load_session,
    _log_access,
    decrypt_passport_for_display,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["immigration-gdpr"])

# Statutory window to respond to a data-subject request (GDPR Art. 12(3)).
ERASURE_RESPONSE_DAYS = 30
# Abuse guard: a full PII export is expensive and sensitive.
MAX_EXPORTS_PER_24H = 3


class ErasureRequestBody(BaseModel):
    reason: Optional[str] = None


class ProcessErasureBody(BaseModel):
    request_id: str
    decision: str  # 'approve' | 'reject'
    review_notes: Optional[str] = None


def _assert_employee_owns_case(case_id: str, employee_id: str) -> None:
    """Raise 403 unless the authenticated employee owns this relocation case."""
    with db.engine.begin() as conn:
        owns = conn.execute(
            text("""
                SELECT 1 FROM public.case_assignments
                WHERE (id = :case_id OR case_id = :case_id)
                  AND employee_user_id = :employee_id
                LIMIT 1
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).first()
    if not owns:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this relocation case.",
        )


def _decrypt_passport(profile: Dict[str, Any]) -> "PassportDecryption":
    """Decrypt passport_number for the owner's view, or withhold it.

    [AIQ-1802] Previously left the ciphertext in place on failure, which put an
    unreadable blob into the Article 15 subject-access PDF. The caller now surfaces the
    withholding explicitly — a silent omission is its own Art. 15 problem, because the
    subject cannot tell a field they never supplied from one we could not return.
    """
    return decrypt_passport_for_display(profile)


@router.get("/employee/cases/{case_id}/my-data/export")
def export_my_data(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """GDPR Art. 15 — stream a fresh PDF of all personal data held for this case.

    The PDF is generated in-memory and never stored. Rate-limited to
    MAX_EXPORTS_PER_24H per employee per case.
    """
    employee_id = current_user["id"]
    _assert_employee_owns_case(case_id, employee_id)

    # Rate limit: count this employee's export events in the last 24h.
    with db.engine.begin() as conn:
        recent = conn.execute(
            text("""
                SELECT count(*) FROM public.data_access_log
                WHERE case_id = :case_id
                  AND accessed_by_user_id = :employee_id
                  AND action = 'export'
                  AND accessed_at > NOW() - INTERVAL '24 hours'
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).scalar()
    if (recent or 0) >= MAX_EXPORTS_PER_24H:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Export limit reached ({MAX_EXPORTS_PER_24H} per 24 hours). Try again later.",
        )

    profile = _load_profile_for_case_employee(case_id, employee_id)
    profile_id = profile.get("id") if profile else None
    withheld_fields: List[str] = []
    if profile:
        decryption = _decrypt_passport(profile)
        profile = decryption.profile
        if decryption.withheld:
            # Say so in the PDF. An Art. 15 response that quietly drops a field is
            # indistinguishable, to the subject, from one where we hold no such data.
            withheld_fields.append("passport_number")

    session = _load_session(case_id, employee_id) or {}
    interview_answers = session.get("answers") or {}

    # Record the export BEFORE reading the access log, so the PDF's access-log
    # section reflects this very export (Art. 15 access is itself processing).
    _log_access(
        case_id=case_id,
        profile_id=profile_id,
        user_id=employee_id,
        role="employee",
        action="export",
        fields=["full_profile", "interview_answers", "consent_records", "access_log"],
        purpose="subject_access_request",
    )

    with db.engine.begin() as conn:
        consent_records = [dict(r) for r in conn.execute(
            text("""
                SELECT purpose, consented, consent_version, consented_at,
                       withdrawn_at, withdrawn_reason, created_at
                FROM public.consent_records
                WHERE case_id = :case_id AND employee_id = :employee_id
                ORDER BY created_at
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().all()]

        access_log = [dict(r) for r in conn.execute(
            text("""
                SELECT accessed_at, accessed_by_role, action, fields_accessed,
                       purpose, vendor_name
                FROM public.data_access_log
                WHERE case_id = :case_id
                  AND (profile_id = :profile_id OR accessed_by_user_id = :employee_id)
                ORDER BY accessed_at DESC
                LIMIT 200
            """),
            {"case_id": case_id, "profile_id": profile_id, "employee_id": employee_id},
        ).mappings().all()]

    pdf_bytes = build_data_export_pdf(
        case_id=case_id,
        employee_id=employee_id,
        profile=profile,
        interview_answers=interview_answers,
        consent_records=consent_records,
        access_log=access_log,
        generated_at=datetime.now(timezone.utc),
        withheld_fields=withheld_fields,
    )

    filename = f"relopass-data-export-{case_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/employee/cases/{case_id}/my-data/erasure-request", status_code=status.HTTP_201_CREATED)
def request_erasure(
    case_id: str,
    body: ErasureRequestBody = ErasureRequestBody(),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """GDPR Art. 17 — file an erasure request. Does NOT delete; HR/admin reviews it (IMM-18)."""
    employee_id = current_user["id"]
    _assert_employee_owns_case(case_id, employee_id)

    profile = _load_profile_for_case_employee(case_id, employee_id)
    org_id = profile.get("org_id") if profile else None

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    due = now + timedelta(days=ERASURE_RESPONSE_DAYS)

    with db.engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO public.erasure_requests
                    (id, case_id, employee_id, org_id, status, reason,
                     requested_at, statutory_due_at)
                VALUES
                    (:id, :case_id, :employee_id, :org_id, 'pending', :reason,
                     :requested_at, :due)
            """),
            {
                "id": request_id,
                "case_id": case_id,
                "employee_id": employee_id,
                "org_id": org_id,
                "reason": body.reason,
                "requested_at": now,
                "due": due,
            },
        )
        # [AIQ-650] Canonical audit trail for the GDPR Art. 17 erasure request
        # (the _log_access below is the PII access-log, a separate concern).
        try:
            insert_audit_log(
                conn,
                entity_type="erasure_request",
                entity_id=request_id,
                action_type=ACTION_INSERT,
                actor_type=ACTOR_HUMAN,
                actor_id=employee_id,
                new_value={"event": "erasure_requested", "case_id": case_id},
            )
        except Exception:
            log.exception("audit: erasure-request case=%s", case_id)

    _log_access(
        case_id=case_id,
        profile_id=profile.get("id") if profile else None,
        user_id=employee_id,
        role="employee",
        action="erasure_request",
        fields=["erasure_request"],
        purpose="erasure_request",
    )

    return {
        "request_id": request_id,
        "status": "pending",
        "requested_at": now.isoformat(),
        "statutory_due_at": due.isoformat(),
        "response_window_days": ERASURE_RESPONSE_DAYS,
        "message": (
            "Your erasure request has been recorded and will be reviewed by your HR team. "
            f"You will receive a response within {ERASURE_RESPONSE_DAYS} days."
        ),
    }


# ---------------------------------------------------------------------------
# HR: review & action erasure requests (IMM-18)
# ---------------------------------------------------------------------------

@router.get("/hr/immigration/erasure-requests")
def list_erasure_requests(
    status_filter: str = "pending",
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """HR review queue — erasure requests for this org, defaulting to pending ones."""
    with db.engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT id, case_id, employee_id, status, reason,
                       requested_at, statutory_due_at, reviewed_by, reviewed_at,
                       review_notes, completed_at
                FROM public.erasure_requests
                WHERE org_id = :org_id
                  AND (:status_filter = 'all' OR status = :status_filter)
                ORDER BY requested_at ASC
            """),
            {"org_id": org_id, "status_filter": status_filter},
        ).mappings().all()

    requests = []
    for r in rows:
        row = dict(r)
        for col in ("requested_at", "statutory_due_at", "reviewed_at", "completed_at"):
            v = row.get(col)
            if hasattr(v, "isoformat"):
                row[col] = v.isoformat()
        requests.append(row)

    pending_count = sum(1 for r in requests if r["status"] == "pending")
    return {"requests": requests, "pending_count": pending_count}


@router.post("/hr/cases/{case_id}/immigration/process-erasure-request")
def process_erasure_request(
    case_id: str,
    body: ProcessErasureBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """HR/admin actions a pending erasure request.

    On 'approve': anonymise every immigration profile on the case in place
    (fn_anonymise_imm_profile NULLs all PII, keeps the audit skeleton) and mark
    the request completed. On 'reject': record the decision and notes only.
    """
    decision = body.decision.lower().strip()
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'reject'.")

    reviewer_id = hr_user["id"]
    now = datetime.now(timezone.utc)

    with db.engine.begin() as conn:
        req = conn.execute(
            text("""
                SELECT id, status FROM public.erasure_requests
                WHERE id = :request_id AND case_id = :case_id AND org_id = :org_id
                LIMIT 1
            """),
            {"request_id": body.request_id, "case_id": case_id, "org_id": org_id},
        ).mappings().first()
        if not req:
            raise HTTPException(status_code=404, detail="Erasure request not found for this case.")
        if req["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Request already {req['status']} — only pending requests can be actioned.",
            )

        anonymised = 0
        if decision == "approve":
            profile_ids = [
                r[0] for r in conn.execute(
                    text("SELECT id FROM public.imm_employee_profiles WHERE case_id = :case_id"),
                    {"case_id": case_id},
                ).all()
            ]
            for pid in profile_ids:
                conn.execute(
                    text("SELECT public.fn_anonymise_imm_profile(:pid)"),
                    {"pid": pid},
                )
                anonymised += 1

            conn.execute(
                text("""
                    UPDATE public.erasure_requests
                    SET status = 'completed', reviewed_by = :reviewer, reviewed_at = :now,
                        review_notes = :notes, completed_at = :now
                    WHERE id = :request_id
                """),
                {"reviewer": reviewer_id, "now": now,
                 "notes": body.review_notes, "request_id": body.request_id},
            )
            new_status = "completed"
        else:
            conn.execute(
                text("""
                    UPDATE public.erasure_requests
                    SET status = 'rejected', reviewed_by = :reviewer, reviewed_at = :now,
                        review_notes = :notes
                    WHERE id = :request_id
                """),
                {"reviewer": reviewer_id, "now": now,
                 "notes": body.review_notes, "request_id": body.request_id},
            )
            new_status = "rejected"

        # [AIQ-650] Audit the HR/admin erasure decision — approval triggers
        # irreversible PII anonymisation, so accountability is critical.
        try:
            insert_audit_log(
                conn,
                entity_type="erasure_request",
                entity_id=body.request_id,
                action_type=ACTION_UPDATE,
                actor_type=ACTOR_HUMAN,
                actor_id=reviewer_id,
                new_value={
                    "event": f"erasure_{new_status}",
                    "case_id": case_id,
                    "profiles_anonymised": anonymised,
                },
            )
        except Exception:
            log.exception(
                "audit: process-erasure case=%s req=%s", case_id, body.request_id
            )

    return {
        "request_id": body.request_id,
        "status": new_status,
        "profiles_anonymised": anonymised,
        "reviewed_by": reviewer_id,
        "reviewed_at": now.isoformat(),
    }
