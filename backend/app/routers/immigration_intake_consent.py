"""
immigration_intake_consent.py — consent + corridor-requirements routes
extracted from immigration.py (AUDIT-B9-imm-3, part 1 of 3).

Houses 3 endpoints:
  GET  /api/hr/cases/{case_id}/immigration-requirements   (corridor lookup)
  POST /api/hr/cases/{case_id}/immigration-consent        (HR-side consent)
  POST /api/employee/cases/{case_id}/consent              (Employee self-consent)

DORMANT: this router is not yet wired into backend/app/main.py. The
canonical registration still happens via immigration.py until imm-6
performs the final switchover. Keep both in sync until then.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.immigration_requirement_service import (
    evaluate_risks,
    get_requirements,
    get_timeline_days,
)
from ..services.immigration_service import (
    _check_consent,
    _get_case_details,
    _log_access,
    _now_iso,
)

# Pydantic models — imported from immigration.py until imm-6 relocates them to
# a shared schemas module. Keep the source of truth in immigration.py for now.
from .immigration import ConsentBody, CONSENT_TEXT_VERSION

router = APIRouter(prefix="/api", tags=["immigration-intake-consent"])


@router.get("/hr/cases/{case_id}/immigration-requirements")
def get_immigration_requirements(
    case_id: str,
    visa_type: str = "blue_card",
    corridor_from: Optional[str] = None,
    corridor_to: Optional[str] = None,
    employee_type: str = "any",
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    Return document requirements for this case's corridor × visa_type.
    Corridor can be passed explicitly or derived from the case record.
    Also returns risk flags if an employee_profile exists for the case.
    """
    # Derive corridor from case if not supplied
    if not corridor_from or not corridor_to:
        case = _get_case_details(case_id, org_id)
        if case:
            corridor_from = corridor_from or case.get("origin_country") or "FR"
            corridor_to = corridor_to or case.get("dest_country") or "DE"
        else:
            corridor_from = corridor_from or "FR"
            corridor_to = corridor_to or "DE"

    requirements = get_requirements(corridor_from, corridor_to, visa_type, employee_type)

    # Load employee profile if available for risk evaluation
    employee_profile = _load_profile_for_case(case_id)
    risk_flags: List[RiskFlag] = []
    move_date_obj = None

    if employee_profile:
        move_date_str = employee_profile.get("_move_date")
        if move_date_str:
            try:
                move_date_obj = date.fromisoformat(move_date_str[:10])
            except (ValueError, TypeError):
                pass
        risk_flags = evaluate_risks(employee_profile, requirements, move_date_obj)

    _log_access(
        case_id=case_id,
        profile_id=employee_profile.get("id") if employee_profile else None,
        user_id=hr_user["id"],
        role="hr",
        action="view",
        fields=["immigration_requirements"],
    )

    return {
        "corridor_from": corridor_from,
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "requirements": [
            {
                "document_type": r.document_type,
                "document_name": r.document_name,
                "is_required": r.is_required,
                "freshness_days": r.freshness_days,
                "requires_apostille": r.requires_apostille,
                "apostille_countries": r.apostille_countries,
                "requires_translation": r.requires_translation,
                "translation_languages": r.translation_languages,
                "can_be_prefilled": r.can_be_prefilled,
                "can_be_ocr_extracted": r.can_be_ocr_extracted,
                "typical_processing_days": r.typical_processing_days,
                "book_early_flag": r.book_early_flag,
                "book_early_reason": r.book_early_reason,
                "success_tips": r.success_tips,
                "common_rejection_reasons": r.common_rejection_reasons,
                "form_url": r.form_url,
            }
            for r in requirements
        ],
        "risk_flags": [
            {
                "flag_type": f.flag_type,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "recommended_action": f.recommended_action,
                "deadline": f.deadline.isoformat() if f.deadline else None,
            }
            for f in risk_flags
        ],
        "estimated_timeline_days": get_timeline_days(requirements),
        "document_count": len(requirements),
    }


# ---------------------------------------------------------------------------
# HR: POST /api/hr/cases/{case_id}/immigration-consent
# ---------------------------------------------------------------------------

@router.post("/hr/cases/{case_id}/immigration-consent", status_code=status.HTTP_201_CREATED)
def record_consent(
    case_id: str,
    body: ConsentBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    HR records GDPR consent on behalf of the employee (or employee self-records).
    Creates a row in consent_records for each purpose in body.purposes.
    Returns the consent_record_id for the immigration_processing purpose.
    """
    if not body.purposes:
        raise HTTPException(status_code=422, detail="At least one purpose required.")

    now = _now_iso()
    primary_id = None

    for purpose in body.purposes:
        record_id = str(uuid.uuid4())
        # Hash the consent text version as proof of what was shown
        text_hash = body.consent_text_hash or hashlib.sha256(
            f"{CONSENT_TEXT_VERSION}:{purpose}".encode()
        ).hexdigest()

        with db.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO public.consent_records
                        (id, employee_id, case_id, purpose, consented,
                         consent_version, consent_text_hash, consented_at)
                    VALUES
                        (:id, :employee_id, :case_id, :purpose, TRUE,
                         :version, :hash, :now)
                """),
                {
                    "id": record_id,
                    "employee_id": body.employee_id,
                    "case_id": case_id,
                    "purpose": purpose,
                    "version": CONSENT_TEXT_VERSION,
                    "hash": text_hash,
                    "now": now,
                },
            )
        if purpose == "immigration_processing":
            primary_id = record_id

    _log_access(
        case_id=case_id,
        profile_id=None,
        user_id=hr_user["id"],
        role="hr",
        action="consent_record",
        fields=body.purposes,
    )

    return {
        "consent_record_id": primary_id,
        "purposes_recorded": body.purposes,
        "consent_version": CONSENT_TEXT_VERSION,
        "recorded_at": now,
    }


# ---------------------------------------------------------------------------
# HR: GET /api/hr/cases/{case_id}/profile  (read-only HR view — no PII)
# ---------------------------------------------------------------------------


@router.post("/employee/cases/{case_id}/consent", status_code=status.HTTP_201_CREATED)
def record_consent_employee(
    case_id: str,
    body: ConsentBody,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Employee self-records GDPR consent for their own immigration case.
    Creates a row in consent_records for each purpose in body.purposes.
    Returns the consent_record_id for the immigration_processing purpose.

    The employee_id in the body must match the authenticated user to prevent
    one employee recording consent on behalf of another.
    """
    employee_id = current_user["id"]

    # Verify the employee_id in the body matches the authenticated user
    if body.employee_id != employee_id:
        raise HTTPException(
            status_code=403,
            detail="employee_id in request body must match the authenticated user.",
        )

    if not body.purposes:
        raise HTTPException(status_code=422, detail="At least one purpose required.")

    now = _now_iso()
    primary_id = None

    for purpose in body.purposes:
        record_id = str(uuid.uuid4())
        text_hash = body.consent_text_hash or hashlib.sha256(
            f"{CONSENT_TEXT_VERSION}:{purpose}".encode()
        ).hexdigest()

        with db.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO public.consent_records
                        (id, employee_id, case_id, purpose, consented,
                         consent_version, consent_text_hash, consented_at)
                    VALUES
                        (:id, :employee_id, :case_id, :purpose, TRUE,
                         :version, :hash, :now)
                """),
                {
                    "id": record_id,
                    "employee_id": employee_id,
                    "case_id": case_id,
                    "purpose": purpose,
                    "version": CONSENT_TEXT_VERSION,
                    "hash": text_hash,
                    "now": now,
                },
            )
        if purpose == "immigration_processing":
            primary_id = record_id

    _log_access(
        case_id=case_id,
        profile_id=None,
        user_id=employee_id,
        role="employee",
        action="consent_record",
        fields=body.purposes,
    )

    return {
        "consent_record_id": primary_id,
        "purposes_recorded": body.purposes,
        "consent_version": CONSENT_TEXT_VERSION,
        "recorded_at": now,
    }


