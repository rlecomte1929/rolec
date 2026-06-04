"""
immigration_gdpr.py — GDPR subject-rights routes extracted from immigration.py
(AUDIT-B9-imm-5), implemented under IMM-17.

Houses 2 endpoints:
  GET  /api/employee/cases/{case_id}/my-data/export             (IMM-17, Art. 15)
  POST /api/employee/cases/{case_id}/my-data/erasure-request    (IMM-17, files Art. 17 request)

The erasure request only records intent — the actual deletion + retention automation
land in IMM-18.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db
from ..services.gdpr_export_service import build_data_export_pdf
from ..services.immigration_service import (
    _get_encryption_key,
    _load_profile_for_case_employee,
    _load_session,
    _log_access,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["immigration-gdpr"])

# Statutory window to respond to a data-subject request (GDPR Art. 12(3)).
ERASURE_RESPONSE_DAYS = 30
# Abuse guard: a full PII export is expensive and sensitive.
MAX_EXPORTS_PER_24H = 3


class ErasureRequestBody(BaseModel):
    reason: Optional[str] = None


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


def _decrypt_passport(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the profile with passport_number decrypted for the owner's view."""
    p = dict(profile)
    if p.get("passport_number"):
        try:
            enc_key = _get_encryption_key()
            with db.engine.begin() as conn:
                row = conn.execute(
                    text("SELECT pgp_sym_decrypt(:enc::bytea, :key) AS decrypted"),
                    {"enc": p["passport_number"], "key": enc_key},
                ).mappings().first()
            if row:
                p["passport_number"] = row["decrypted"]
        except Exception:
            pass  # leave encrypted form if decryption fails
    return p


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
    profile = _decrypt_passport(profile) if profile else None

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
