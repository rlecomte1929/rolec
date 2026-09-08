"""
immigration_intake_consent.py — consent + corridor-requirements routes.

Houses 3 endpoints:
  GET  /api/hr/cases/{case_id}/immigration-requirements   (corridor lookup)
  POST /api/hr/cases/{case_id}/immigration-consent        (HR-side consent)
  POST /api/employee/cases/{case_id}/consent              (Employee self-consent)
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTOR_HUMAN,
    insert_audit_log,
)
from ..services.immigration_regime import default_visa_type_for_destination
from ..services.immigration_requirement_service import (
    RiskFlag,
    evaluate_risks,
    get_requirements,
    get_timeline_days,
)
from ..services.immigration_service import (
    _check_consent,
    _get_case_details,
    _load_profile_for_case,
    _log_access,
    _now_iso,
)

log = logging.getLogger(__name__)

CONSENT_TEXT_VERSION = "v1.0-2026-05"


class ConsentBody(BaseModel):
    employee_id: str
    purposes: List[str]
    consent_text_hash: Optional[str] = None


class WithdrawConsentBody(BaseModel):
    purpose: str
    reason: Optional[str] = None

router = APIRouter(prefix="/api", tags=["immigration-intake-consent"])


def _uncovered_response(
    corridor_from: Optional[str],
    corridor_to: Optional[str],
    visa_type: Optional[str],
) -> Dict[str, Any]:
    """
    Structured fail-closed payload for a corridor we cannot answer for —
    either the case has no origin/destination geography, or the corridor ×
    visa_type combination is not seeded in immigration_requirements.

    Returns HTTP 200 (graceful degrade) with covered=False so the caller can
    distinguish "no coverage" from a real, populated checklist. Never emits a
    default corridor or a default timeline — that silent FR→DE fallback was the
    bug this guards against (AIQ-832 / F1).
    """
    corridor = (
        f"{corridor_from}→{corridor_to}"
        if corridor_from and corridor_to
        else None
    )
    return {
        "covered": False,
        "coverage_reason": "corridor_not_supported",
        "corridor": corridor,
        "corridor_from": corridor_from,
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "requirements": [],
        "risk_flags": [],
        "estimated_timeline_days": None,
        "document_count": 0,
    }


def _log_view_access(case_id: str, hr_user: Dict[str, Any]) -> None:
    """
    Record an immigration-requirements view in the access audit trail.

    The fail-closed paths return before any employee profile is loaded, so
    profile_id is None — but the access still happened and must be logged, just
    as the covered path logs it (parity preserved from before the fail-closed
    early returns were added).
    """
    _log_access(
        case_id=case_id,
        profile_id=None,
        user_id=hr_user["id"],
        role="hr",
        action="view",
        fields=["immigration_requirements"],
    )


@router.get("/hr/cases/{case_id}/immigration-requirements")
def get_immigration_requirements(
    case_id: str,
    # [AIQ-1833] No default — resolved from the corridor below.
    visa_type: Optional[str] = None,
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
    # Derive corridor from the case when not supplied — with NO silent country
    # defaults. A case lacking origin/destination geography fails closed rather
    # than resolving to the previously hardcoded FR→DE fallback corridor (AIQ-832).
    if not corridor_from or not corridor_to:
        case = _get_case_details(case_id, org_id)
        if case:
            corridor_from = corridor_from or case.get("origin_country")
            corridor_to = corridor_to or case.get("dest_country")

    # [AIQ-1833] Resolve the visa type from the destination instead of defaulting to
    # blue_card. Ireland and Denmark are the two EU states outside Directive 2021/1883
    # and issue no Blue Card; nor do non-EU destinations such as Norway. Reporting one
    # anyway was a confident wrong answer about immigration.
    if visa_type is None:
        visa_type = default_visa_type_for_destination(corridor_to)

    # Fail closed: missing geography cannot be answered authoritatively.
    if not corridor_from or not corridor_to:
        _log_view_access(case_id, hr_user)
        return _uncovered_response(corridor_from, corridor_to, visa_type)

    # Fail closed: no determinable visa type for this destination. Querying with None
    # would match nothing regardless — say so explicitly rather than implying a permit.
    if not visa_type:
        _log_view_access(case_id, hr_user)
        return _uncovered_response(corridor_from, corridor_to, visa_type)

    requirements = get_requirements(corridor_from, corridor_to, visa_type, employee_type)

    # Fail closed: an unseeded corridor returns no rows — report it as such
    # instead of an empty checklist that looks like "nothing required".
    if not requirements:
        # DOC-1 corridor fallback (2026-08-22): the immigration_requirements DOCUMENT table
        # has no rows for some corridors that DO carry verified requirement_items content
        # (e.g. ES->IE, already served by /api/public/corridor-requirements). Surface that
        # same corridor content here, clearly marked as the fallback, instead of a bare
        # "not covered". This never invents a default corridor: corridor_from/corridor_to
        # are already resolved and non-null here, so the AIQ-832 fail-closed guarantee holds.
        # Falls through to _uncovered_response when no corridor content exists either.
        _log_view_access(case_id, hr_user)
        try:
            from ..services.corridor_requirements_service import (
                list_corridor_requirement_items,
            )
            from ..services.corridor_requirements_fallback import build_covered_fallback
            _corridor_items = list_corridor_requirement_items(
                to=corridor_to, employee_type=employee_type,
            )
        except Exception:
            log.exception(
                "corridor_requirements fallback failed for %s->%s", corridor_from, corridor_to
            )
            _corridor_items = []
        if _corridor_items:
            return build_covered_fallback(
                corridor_from, corridor_to, visa_type, _corridor_items
            )
        return _uncovered_response(corridor_from, corridor_to, visa_type)

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

    # IMM-15: surface a minimal slice of the employee's situation so the HR
    # immigration panel can pre-fill a vendor RFQ (nationality + dependents).
    # Sensitive identifiers (passport, DOB) are deliberately NOT included.
    employee_nationality = (employee_profile or {}).get("nationality") or None
    dependents = (employee_profile or {}).get("dependents") or []
    dependents_count = len(dependents) if isinstance(dependents, list) else 0

    _log_access(
        case_id=case_id,
        profile_id=employee_profile.get("id") if employee_profile else None,
        user_id=hr_user["id"],
        role="hr",
        action="view",
        fields=["immigration_requirements"],
    )

    return {
        "covered": True,
        "coverage_reason": None,
        "corridor": f"{corridor_from}→{corridor_to}",
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
        # IMM-15: case context for vendor RFQ pre-fill
        "employee_nationality": employee_nationality,
        "has_dependents": dependents_count > 0,
        "dependents_count": dependents_count,
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
            try:
                insert_audit_log(
                    conn,
                    entity_type="consent_record",
                    entity_id=record_id,
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=hr_user["id"],
                    new_value={"event": "consent_recorded", "purpose": purpose,
                               "case_id": case_id, "on_behalf_of": body.employee_id},
                )
            except Exception:
                log.exception("audit: record_consent(hr) case=%s purpose=%s", case_id, purpose)
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
            try:
                insert_audit_log(
                    conn,
                    entity_type="consent_record",
                    entity_id=record_id,
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=employee_id,
                    new_value={"event": "consent_recorded", "purpose": purpose,
                               "case_id": case_id},
                )
            except Exception:
                log.exception("audit: record_consent(emp) case=%s purpose=%s", case_id, purpose)
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


@router.get("/employee/cases/{case_id}/consent")
def list_consent_employee(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List the employee's own consent records for this case (latest per purpose)."""
    employee_id = current_user["id"]

    with db.engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT DISTINCT ON (purpose)
                       purpose, consented, consent_version,
                       consented_at, withdrawn_at, withdrawn_reason, created_at
                FROM public.consent_records
                WHERE case_id = :case_id AND employee_id = :employee_id
                ORDER BY purpose, created_at DESC
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().all()

    records = []
    for r in rows:
        d = dict(r)
        d["active"] = bool(d.get("consented")) and d.get("withdrawn_at") is None
        records.append(d)

    return {"consent_records": records}


@router.post("/employee/cases/{case_id}/consent/withdraw")
def withdraw_consent_employee(
    case_id: str,
    body: WithdrawConsentBody,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    GDPR Art. 7(3) — employee withdraws consent for a given purpose.

    Appends a withdrawal row (consented=FALSE, withdrawn_at=now); it does NOT update the
    original grant. `consent_records` is an append-only ledger and a trigger blocks UPDATE
    and DELETE for every role including service_role, so the UPDATE this used to issue
    raised for every caller — meaning withdrawal was impossible in production and the 404
    branch below was unreachable (AIQ-1803). The trigger's own error message names the
    required pattern; `outcome_consent.record_outcome_consent` is the in-repo reference.

    Returns 404 if consent is not currently held for the purpose — read from the LATEST
    ledger row, not from "any un-withdrawn row", so a re-grant after a withdrawal is
    withdrawable again.
    """
    employee_id = current_user["id"]
    now = _now_iso()

    with db.engine.begin() as conn:
        # The latest row is the current state. Carry its version/hash onto the withdrawal
        # so the ledger records which consent text was withdrawn — both columns are NOT
        # NULL, and inventing a value here would corrupt the audit trail.
        current = conn.execute(
            text("""
                SELECT consented, withdrawn_at, consent_version, consent_text_hash
                FROM public.consent_records
                WHERE case_id = :case_id
                  AND employee_id = :employee_id
                  AND purpose = :purpose
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"case_id": case_id, "employee_id": employee_id, "purpose": body.purpose},
        ).mappings().first()

        held = bool(current and current["consented"] and current["withdrawn_at"] is None)

        if held:
            record_id = str(uuid.uuid4())
            conn.execute(
                text("""
                    INSERT INTO public.consent_records
                        (id, employee_id, case_id, purpose, consented,
                         consent_version, consent_text_hash, withdrawn_at, withdrawn_reason)
                    VALUES
                        (:id, :employee_id, :case_id, :purpose, FALSE,
                         :version, :hash, :now, :reason)
                """),
                {
                    "id": record_id,
                    "employee_id": employee_id,
                    "case_id": case_id,
                    "purpose": body.purpose,
                    "version": current["consent_version"],
                    "hash": current["consent_text_hash"],
                    "now": now,
                    "reason": body.reason,
                },
            )
            try:
                insert_audit_log(
                    conn,
                    entity_type="consent_record",
                    entity_id=record_id,
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=employee_id,
                    new_value={"event": "consent_withdrawn", "purpose": body.purpose,
                               "case_id": case_id},
                )
            except Exception:
                log.exception("audit: withdraw_consent case=%s purpose=%s", case_id, body.purpose)

    if not held:
        raise HTTPException(
            status_code=404,
            detail=f"No active consent on record for purpose '{body.purpose}'.",
        )

    _log_access(
        case_id=case_id,
        profile_id=None,
        user_id=employee_id,
        role="employee",
        action="consent_withdraw",
        fields=[body.purpose],
    )

    return {
        "purpose": body.purpose,
        "withdrawn": True,
        # Always 1: the ledger is append-only, so a withdrawal is one new row that
        # supersedes whatever came before it — not a count of rows mutated.
        "records_withdrawn": 1,
        "withdrawn_at": now,
    }


