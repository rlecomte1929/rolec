"""
outcome_consent.py — per-case opt-in to anonymized outcome sharing (P1-07c / AIQ-686).

GDPR Art. 6 legal basis for the AIQ-685 outcome flywheel: the relocating employee
explicitly consents (per case) to ReloPass using their *anonymized* relocation
outcome to improve the AI. Without a consented record, ``outcome_extractor``
writes nothing for that case.

Endpoints:
  POST /api/employee/cases/{case_id}/outcome-consent   {consented: bool}
  GET  /api/employee/cases/{case_id}/outcome-consent    -> {consented: bool|null}

Storage: the existing per-case, per-purpose ``public.consent_records`` ledger
(append-only, withdrawable) under purpose ``outcome_sharing_anonymized`` —
distinct from privacy_consents.py (Art. 13 notice) and immigration_intake_consent.py
(immigration_processing). The employee is resolved/validated against
``case_assignments.employee_user_id`` (tenant scoping).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ..services.outcome_extractor import OUTCOME_CONSENT_PURPOSE
from ...database import db

router = APIRouter(prefix="/api/employee/cases", tags=["outcome-consent"])

# Bump when the consent copy materially changes (re-consent on next surface).
OUTCOME_CONSENT_VERSION = "outcome-v1-2026-06-29"
OUTCOME_CONSENT_TEXT = (
    "I agree that ReloPass may use my anonymized relocation outcome "
    "(no name, no contact details, no documents) to improve its AI. "
    "This is optional and I can withdraw it at any time."
)
_CONSENT_TEXT_HASH = hashlib.sha256(OUTCOME_CONSENT_TEXT.encode("utf-8")).hexdigest()


class OutcomeConsentBody(BaseModel):
    consented: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_case_employee(case_id: str) -> Optional[str]:
    """The employee_user_id assigned to this case, or None if no assignment."""
    assignment = db.get_assignment_by_case_id(case_id)
    if not assignment:
        return None
    return assignment.get("employee_user_id")


def _caller_owns_case(current_user: Dict[str, Any], employee_user_id: Optional[str]) -> bool:
    """The caller must be the employee assigned to the case (tenant scoping)."""
    if not employee_user_id:
        return False
    candidates = {
        str(current_user.get("id") or "").strip(),
        str(current_user.get("auth_uuid") or "").strip(),
    }
    candidates.discard("")
    return str(employee_user_id).strip() in candidates


@router.post("/{case_id}/outcome-consent", status_code=201)
def set_outcome_consent(
    case_id: str,
    body: OutcomeConsentBody,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Record (or withdraw) the employee's outcome-sharing consent for a case.

    Append-only: each call inserts a fresh ``consent_records`` row; the most
    recent non-withdrawn row is authoritative in ``has_outcome_consent``.
    """
    employee_user_id = _resolve_case_employee(case_id)
    if not _caller_owns_case(current_user, employee_user_id):
        # 404 (not 403) so we don't confirm the existence of someone else's case.
        raise HTTPException(status_code=404, detail="Case not found")

    now = _now_iso()
    record_id = str(uuid.uuid4())
    consented = bool(body.consented)

    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO consent_records "
                "(id, employee_id, case_id, purpose, consented, consent_version, "
                " consent_text_hash, consented_at, withdrawn_at, withdrawn_reason, "
                " ip_address, user_agent, created_at) "
                "VALUES "
                "(:id, :employee_id, :case_id, :purpose, :consented, :version, "
                " :text_hash, :consented_at, :withdrawn_at, :withdrawn_reason, "
                " :ip, :ua, :created_at)"
            ),
            {
                "id": record_id,
                "employee_id": employee_user_id,
                "case_id": case_id,
                "purpose": OUTCOME_CONSENT_PURPOSE,
                "consented": consented,
                "version": OUTCOME_CONSENT_VERSION,
                "text_hash": _CONSENT_TEXT_HASH,
                "consented_at": now if consented else None,
                "withdrawn_at": None if consented else now,
                "withdrawn_reason": None if consented else "employee_opt_out",
                "ip": request.client.host if request.client else None,
                "ua": request.headers.get("user-agent"),
                "created_at": now,
            },
        )

    return {
        "consent_id": record_id,
        "case_id": case_id,
        "purpose": OUTCOME_CONSENT_PURPOSE,
        "consented": consented,
        "consent_version": OUTCOME_CONSENT_VERSION,
        "recorded_at": now,
    }


@router.get("/{case_id}/outcome-consent")
def get_outcome_consent(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Latest outcome-sharing consent state for the case (for the opt-in UI)."""
    employee_user_id = _resolve_case_employee(case_id)
    if not _caller_owns_case(current_user, employee_user_id):
        raise HTTPException(status_code=404, detail="Case not found")

    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT consented, withdrawn_at, consent_version FROM consent_records "
                "WHERE case_id = :cid AND purpose = :purpose "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": case_id, "purpose": OUTCOME_CONSENT_PURPOSE},
        ).mappings().first()

    if not row:
        consented: Optional[bool] = None
    else:
        consented = bool(row["consented"]) and row["withdrawn_at"] is None

    return {
        "case_id": case_id,
        "purpose": OUTCOME_CONSENT_PURPOSE,
        "consented": consented,
        "consent_version": OUTCOME_CONSENT_VERSION,
    }
