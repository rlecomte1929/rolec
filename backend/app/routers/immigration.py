"""
Immigration router — IMM-02, IMM-04

Endpoints:

  HR-facing:
    GET  /api/hr/cases/{case_id}/immigration-requirements
    POST /api/hr/cases/{case_id}/immigration-consent
    GET  /api/hr/cases/{case_id}/profile           (read-only HR view)
    PATCH /api/hr/cases/{case_id}/profile/hr-fields

  Employee-facing:
    GET  /api/employee/cases/{case_id}/profile
    PUT  /api/employee/cases/{case_id}/profile
    POST /api/employee/cases/{case_id}/profile/ocr-passport   (stub — IMM-05)
    GET  /api/employee/cases/{case_id}/interview/next         (stub — IMM-06)
    POST /api/employee/cases/{case_id}/interview/answer       (stub — IMM-06)
    GET  /api/employee/cases/{case_id}/interview/status       (stub — IMM-06)
    GET  /api/employee/cases/{case_id}/my-data/export         (stub — IMM-17)
    POST /api/employee/cases/{case_id}/my-data/erasure-request (stub — IMM-18)

  Immigration milestones:
    GET  /api/hr/cases/{case_id}/immigration/milestones
    POST /api/hr/cases/{case_id}/immigration/milestones
    PATCH /api/hr/cases/{case_id}/immigration/milestones/{milestone_id}
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
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
from ..services.ocr_passport_extractor import (
    ConflictRecord,
    MrzValidationResult,
    PassportExtractionResult,
    detect_conflicts,
    extract_passport,
    save_ocr_to_vault,
    validate_mrz,
    _upload_passport_image,
)
from ..services.immigration_requirement_service import (
    RequirementResult,
    RiskFlag,
    evaluate_risks,
    get_requirements,
    get_timeline_days,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["immigration"])

CONSENT_TEXT_VERSION = "v1.0-2026-05"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ConsentBody(BaseModel):
    employee_id: str
    purposes: List[str]          # ['immigration_processing'] or add 'vendor_sharing'
    consent_text_hash: Optional[str] = None   # SHA-256 of displayed text


class HrProfileFields(BaseModel):
    employer_name: Optional[str] = None
    employer_reg_number: Optional[str] = None
    employer_address: Optional[Dict[str, Any]] = None
    job_title: Optional[str] = None
    job_title_local: Optional[str] = None
    employment_start_date: Optional[str] = None
    salary_amount: Optional[float] = None
    salary_currency: Optional[str] = None
    contract_type: Optional[str] = None


class EmployeeProfileUpdate(BaseModel):
    legal_first_name: Optional[str] = None
    legal_last_name: Optional[str] = None
    middle_names: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    second_nationality: Optional[str] = None
    gender: Optional[str] = None
    passport_number: Optional[str] = None   # app-layer encrypted before save
    passport_expiry: Optional[str] = None
    passport_issue_date: Optional[str] = None
    passport_country: Optional[str] = None
    passport_mrz_line1: Optional[str] = None
    passport_mrz_line2: Optional[str] = None
    existing_visa_type: Optional[str] = None
    existing_visa_expiry: Optional[str] = None
    prior_visa_refusals: Optional[bool] = None
    current_address: Optional[Dict[str, Any]] = None
    address_history: Optional[List[Dict[str, Any]]] = None
    marital_status: Optional[str] = None
    spouse_name: Optional[str] = None
    spouse_nationality: Optional[str] = None
    spouse_dob: Optional[str] = None
    dependents: Optional[List[Dict[str, Any]]] = None
    highest_qualification: Optional[str] = None
    institution: Optional[str] = None
    graduation_year: Optional[int] = None
    degree_anabin_status: Optional[str] = None


class InterviewAnswerBody(BaseModel):
    question_id: str
    answer_value: Any            # str | bool | dict | list — depends on question type
    skip: Optional[bool] = False  # if True, record as explicitly skipped


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_consent(case_id: str, employee_id: str) -> bool:
    """Return True if a valid immigration_processing consent exists for this case+employee."""
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT id FROM public.consent_records
                WHERE case_id    = :case_id
                  AND employee_id = :employee_id
                  AND purpose     = 'immigration_processing'
                  AND consented   = TRUE
                  AND withdrawn_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().first()
    return row is not None


def _log_access(
    case_id: str,
    profile_id: Optional[str],
    user_id: str,
    role: str,
    action: str,
    fields: List[str],
    purpose: str = "immigration_processing",
) -> None:
    """Write an entry to data_access_log. Silently ignores errors (never block the main request)."""
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO public.data_access_log
                        (case_id, profile_id, accessed_by_user_id, accessed_by_role,
                         action, fields_accessed, purpose, accessed_at)
                    VALUES
                        (:case_id, :profile_id, :user_id, :role,
                         :action, :fields, :purpose, NOW())
                """),
                {
                    "case_id": case_id,
                    "profile_id": profile_id,
                    "user_id": user_id,
                    "role": role,
                    "action": action,
                    "fields": fields,
                    "purpose": purpose,
                },
            )
    except Exception as exc:
        log.warning("Failed to write data_access_log: %s", exc)


def _get_case_details(case_id: str, org_id: str) -> Optional[Dict[str, Any]]:
    """Fetch basic case details (corridor) from the assignment record.

    The route parameter is the case_assignments.id (PK), not case_id (FK).
    We try by PK first, then fall back to FK so the helper works in both call sites.
    """
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT ca.id, ca.case_id, ca.employee_user_id,
                       mc.destination_country AS dest_country,
                       mc.origin_country
                FROM public.case_assignments ca
                LEFT JOIN public.mobility_cases mc ON mc.id::text = ca.case_id
                WHERE ca.id = :case_id OR ca.case_id = :case_id
                LIMIT 1
            """),
            {"case_id": case_id},
        ).mappings().first()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# HR: GET /api/hr/cases/{case_id}/immigration-requirements
# ---------------------------------------------------------------------------

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

@router.get("/hr/cases/{case_id}/profile")
def get_profile_hr(
    case_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    HR read-only view of the employee profile.
    Sensitive fields (passport_number, date_of_birth) are masked.
    """
    profile = _load_profile_for_case(case_id)
    if not profile:
        return {"profile": None, "consent_given": False}

    _log_access(
        case_id=case_id,
        profile_id=profile.get("id"),
        user_id=hr_user["id"],
        role="hr",
        action="view",
        fields=["profile_summary"],
    )

    # Mask sensitive fields for HR view
    safe = dict(profile)
    if safe.get("passport_number"):
        safe["passport_number"] = "••••••••"
    if safe.get("date_of_birth"):
        safe["date_of_birth"] = "••••••••"
    if safe.get("passport_mrz_line1"):
        safe["passport_mrz_line1"] = "••••••••"
    if safe.get("passport_mrz_line2"):
        safe["passport_mrz_line2"] = "••••••••"

    return {"profile": safe, "consent_given": True}


# ---------------------------------------------------------------------------
# HR: PATCH /api/hr/cases/{case_id}/profile/hr-fields
# ---------------------------------------------------------------------------

@router.patch("/hr/cases/{case_id}/profile/hr-fields")
def update_profile_hr_fields(
    case_id: str,
    body: HrProfileFields,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    HR sets employment fields in the employee profile.
    All fields set here are marked as 'hr_provided' in field_sources.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update.")

    now = _now_iso()
    profile = _load_profile_for_case(case_id)

    if profile:
        # Update existing profile
        set_clauses = []
        params: Dict[str, Any] = {"case_id": case_id, "now": now}
        for field_name, value in updates.items():
            set_clauses.append(f"{field_name} = :{field_name}")
            params[field_name] = value

        # Update field_sources
        existing_sources = profile.get("field_sources") or {}
        for field_name in updates:
            existing_sources[field_name] = "hr_provided"
        params["field_sources"] = existing_sources
        set_clauses.append("field_sources = :field_sources")
        set_clauses.append("updated_at = :now")

        sql = f"""
            UPDATE public.imm_employee_profiles
            SET {', '.join(set_clauses)}
            WHERE case_id = :case_id
            RETURNING id
        """
        with db.engine.begin() as conn:
            conn.execute(text(sql), params)
    else:
        # No profile yet — create one with just the HR fields
        profile_id = str(uuid.uuid4())
        field_sources = {f: "hr_provided" for f in updates}
        params = {
            "id": profile_id,
            "case_id": case_id,
            "employee_id": "",   # Employee not yet known
            "org_id": org_id,
            "field_sources": field_sources,
            "now": now,
        }
        params.update(updates)
        cols = list(params.keys())
        placeholders = [f":{c}" for c in cols]
        with db.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO public.imm_employee_profiles ({', '.join(cols)})
                    VALUES ({', '.join(placeholders)})
                """),
                params,
            )

    _log_access(
        case_id=case_id,
        profile_id=profile.get("id") if profile else None,
        user_id=hr_user["id"],
        role="hr",
        action="edit",
        fields=list(updates.keys()),
    )

    return {"updated_fields": list(updates.keys()), "source": "hr_provided"}


# ---------------------------------------------------------------------------
# Employee: GET /api/employee/cases/{case_id}/profile
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Employee: POST /api/employee/cases/{case_id}/consent
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


@router.get("/employee/cases/{case_id}/profile")
def get_profile_employee(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Employee reads their own full profile (with consent gate)."""
    employee_id = current_user["id"]

    if not _check_consent(case_id, employee_id):
        raise HTTPException(
            status_code=403,
            detail="No valid immigration consent on record for this case. "
                   "Please complete the consent step first.",
        )

    profile = _load_profile_for_case_employee(case_id, employee_id)
    if not profile:
        return {"profile": None}

    _log_access(
        case_id=case_id,
        profile_id=profile.get("id"),
        user_id=employee_id,
        role="employee",
        action="view",
        fields=["full_profile"],
    )

    # Decrypt passport_number for the employee's own view
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
            pass  # Return encrypted form if decryption fails

    return {"profile": p}


# ---------------------------------------------------------------------------
# Employee: PUT /api/employee/cases/{case_id}/profile
# ---------------------------------------------------------------------------

@router.put("/employee/cases/{case_id}/profile")
def upsert_profile_employee(
    case_id: str,
    body: EmployeeProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Employee upserts their own profile fields.
    Consent must exist. All fields set here are marked 'self_entered'.
    passport_number is encrypted before storage.
    """
    employee_id = current_user["id"]

    if not _check_consent(case_id, employee_id):
        raise HTTPException(
            status_code=403,
            detail="Consent required before submitting immigration data.",
        )

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update.")

    # Encrypt passport_number if provided
    if "passport_number" in updates and updates["passport_number"]:
        try:
            enc_key = _get_encryption_key()
            with db.engine.begin() as conn:
                row = conn.execute(
                    text("SELECT pgp_sym_encrypt(:val, :key) AS encrypted"),
                    {"val": updates["passport_number"], "key": enc_key},
                ).mappings().first()
            if row:
                updates["passport_number"] = row["encrypted"]
        except Exception as exc:
            log.error("passport_number encryption failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to encrypt sensitive data.")

    now = _now_iso()
    profile = _load_profile_for_case_employee(case_id, employee_id)

    if profile:
        existing_sources = profile.get("field_sources") or {}
        for f in updates:
            # Don't overwrite hr_provided fields
            if existing_sources.get(f) != "hr_provided":
                existing_sources[f] = "self_entered"

        set_clauses = []
        params: Dict[str, Any] = {"case_id": case_id, "employee_id": employee_id, "now": now}
        for field_name, value in updates.items():
            if existing_sources.get(field_name) == "hr_provided":
                continue  # HR-locked field — skip
            set_clauses.append(f"{field_name} = :{field_name}")
            params[field_name] = value

        if not set_clauses:
            return {"updated_fields": [], "message": "All fields are HR-provided and locked."}

        params["field_sources"] = existing_sources
        set_clauses.append("field_sources = :field_sources")
        set_clauses.append("updated_at = :now")

        with db.engine.begin() as conn:
            conn.execute(
                text(f"""
                    UPDATE public.imm_employee_profiles
                    SET {', '.join(set_clauses)}
                    WHERE case_id = :case_id AND employee_id = :employee_id
                """),
                params,
            )
    else:
        # Create new profile
        profile_id = str(uuid.uuid4())
        field_sources = {f: "self_entered" for f in updates}
        params = {
            "id": profile_id,
            "case_id": case_id,
            "employee_id": employee_id,
            "org_id": "",
            "field_sources": field_sources,
            "created_at": now,
            "updated_at": now,
        }
        params.update(updates)
        cols = list(params.keys())
        with db.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO public.imm_employee_profiles ({', '.join(cols)})
                    VALUES ({', '.join([f':{c}' for c in cols])})
                """),
                params,
            )

    _log_access(
        case_id=case_id,
        profile_id=profile.get("id") if profile else None,
        user_id=employee_id,
        role="employee",
        action="edit",
        fields=[f for f in updates if f != "passport_number"],
        # Note: 'passport_number' appears in fields_accessed list but value is never logged
    )

    return {"updated_fields": list(updates.keys()), "source": "self_entered"}


# ---------------------------------------------------------------------------
# Immigration milestones
# ---------------------------------------------------------------------------

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

@router.post("/employee/cases/{case_id}/profile/ocr-passport")
async def ocr_passport(
    case_id: str,
    passport_image: UploadFile = File(..., description="Passport photo — JPEG, PNG, or WebP, max 10 MB"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    IMM-05 — Passport OCR upload, extract, validate MRZ, detect conflicts,
    and auto-save extracted fields to imm_employee_profiles.

    Returns extracted fields with per-field confidence, MRZ validation result,
    conflict records, and the updated profile_id.
    Does NOT require the employee to confirm — fields are saved immediately
    with source='ocr' (can be overridden by a subsequent self_entered PUT).
    """
    employee_id = current_user["id"]

    # --- Consent gate ---
    if not _check_consent(case_id, employee_id):
        raise HTTPException(
            status_code=403,
            detail="No valid immigration consent on record for this case. "
                   "Please complete the consent step first.",
        )

    # --- Validate file type and size ---
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_BYTES = 10 * 1024 * 1024  # 10 MB

    content_type = (passport_image.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{content_type}'. Accepted: JPEG, PNG, WebP.",
        )

    image_bytes = await passport_image.read()
    if len(image_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File too large ({len(image_bytes) // 1024} KB). Maximum is 10 MB.",
        )

    # --- Upload to Supabase Storage (non-blocking — failure is logged but not surfaced) ---
    storage_path = _upload_passport_image(case_id, image_bytes, content_type)

    # --- OCR extraction via GPT-4o ---
    try:
        extraction: PassportExtractionResult = await extract_passport(image_bytes, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        log.error("OCR runtime error for case %s: %s", case_id, exc)
        raise HTTPException(status_code=503, detail="OCR service temporarily unavailable.")

    # --- MRZ validation ---
    mrz_result: Optional[MrzValidationResult] = None
    if extraction.mrz_line1 and extraction.mrz_line2:
        mrz_result = validate_mrz(extraction.mrz_line1, extraction.mrz_line2)

    # --- Load existing vault for conflict detection ---
    existing_profile = _load_profile_for_case_employee(case_id, employee_id)
    conflicts: List[ConflictRecord] = []
    if existing_profile:
        conflicts = detect_conflicts(
            extraction,
            existing_profile,
            field_sources=existing_profile.get("field_sources") or {},
        )

    # --- Auto-save to vault ---
    org_id = current_user.get("org_id", "")
    profile_id = save_ocr_to_vault(case_id, employee_id, extraction, org_id)

    # --- Log access ---
    saved_fields = [
        f for f in [
            "legal_first_name", "legal_last_name", "date_of_birth", "gender",
            "place_of_birth", "nationality", "passport_country", "passport_expiry",
            "passport_issue_date", "passport_number", "passport_mrz_line1", "passport_mrz_line2",
        ]
        if getattr(extraction, {
            "legal_first_name": "given_names", "legal_last_name": "surname",
            "passport_country": "issuing_country", "passport_expiry": "expiry_date",
            "passport_issue_date": "issue_date", "passport_mrz_line1": "mrz_line1",
            "passport_mrz_line2": "mrz_line2",
        }.get(f, f), None) is not None
    ]
    _log_access(
        case_id=case_id,
        profile_id=profile_id or (existing_profile.get("id") if existing_profile else None),
        user_id=employee_id,
        role="employee",
        action="ocr_extract",
        fields=saved_fields,
        purpose="immigration_processing",
    )

    return {
        "profile_id": profile_id,
        "storage_path": storage_path,
        "extracted_fields": {
            "surname": extraction.surname,
            "given_names": extraction.given_names,
            "date_of_birth": extraction.date_of_birth,
            "gender": extraction.gender,
            "place_of_birth": extraction.place_of_birth,
            "nationality": extraction.nationality,
            "issuing_country": extraction.issuing_country,
            "passport_number": extraction.passport_number,
            "issue_date": extraction.issue_date,
            "expiry_date": extraction.expiry_date,
            "mrz_line1": extraction.mrz_line1,
            "mrz_line2": extraction.mrz_line2,
        },
        "confidence": extraction.confidence,
        "mrz_validation": {
            "is_valid": mrz_result.is_valid if mrz_result else None,
            "error_fields": mrz_result.error_fields if mrz_result else [],
            "details": mrz_result.details if mrz_result else {},
        } if mrz_result else None,
        "conflicts": [
            {
                "field_name": c.field_name,
                "ocr_value": c.ocr_value,
                "vault_value": c.vault_value,
                "vault_source": c.vault_source,
            }
            for c in conflicts
        ],
        "fields_saved": saved_fields,
    }


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
    employee_id = current_user["id"]

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


@router.get("/employee/cases/{case_id}/my-data/export")
def data_export_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Data export (IMM-17) not yet implemented.")


@router.post("/employee/cases/{case_id}/my-data/erasure-request")
def erasure_request_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Erasure workflow (IMM-18) not yet implemented.")


# ---------------------------------------------------------------------------
# MVG-6 immigration case management (HR create/view + employee checklist)
# ---------------------------------------------------------------------------

VALID_PERMIT_TYPES = {
    "eu_blue_card", "work_permit", "skilled_worker_visa", "eea_registration", "other"
}


class ImmigrationCaseCreate(BaseModel):
    case_id: str
    corridor_from: str
    corridor_to: str
    permit_type: str
    partner_name: Optional[str] = None
    expected_submission_date: Optional[str] = None   # ISO date string yyyy-mm-dd
    expected_grant_date: Optional[str] = None        # ISO date string yyyy-mm-dd


def _serialize_imm_case(row: Any) -> Dict[str, Any]:
    """Convert a DB row from immigration_cases to a JSON-safe dict."""
    r = dict(row)
    for col in ("created_at", "updated_at", "expected_submission_date",
                "expected_grant_date", "permit_expiry_date"):
        v = r.get(col)
        if hasattr(v, "isoformat"):
            r[col] = v.isoformat()
    # Ensure UUIDs are strings
    for col in ("id", "case_id", "created_by_hr_id"):
        if r.get(col) is not None:
            r[col] = str(r[col])
    return r


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
        # Employees must own the relocation case
        employee_id = current_user["id"]
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

def _load_profile_for_case(case_id: str) -> Optional[Dict[str, Any]]:
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT * FROM public.imm_employee_profiles
                WHERE case_id = :case_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"case_id": case_id},
        ).mappings().first()
    if not row:
        return None
    result = dict(row)
    for col in ("created_at", "updated_at", "passport_expiry", "date_of_birth",
                "employment_start_date", "retention_expires_at"):
        v = result.get(col)
        if hasattr(v, "isoformat"):
            result[col] = v.isoformat()
    return result


def _load_profile_for_case_employee(case_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT * FROM public.imm_employee_profiles
                WHERE case_id = :case_id AND employee_id = :employee_id
                LIMIT 1
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().first()
    if not row:
        return None
    result = dict(row)
    for col in ("created_at", "updated_at", "passport_expiry", "date_of_birth",
                "employment_start_date", "retention_expires_at"):
        v = result.get(col)
        if hasattr(v, "isoformat"):
            result[col] = v.isoformat()
    return result


def _ts(v: Any) -> Optional[str]:
    """Coerce a datetime/string to ISO string, or None."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


# ---------------------------------------------------------------------------
# Interview session DB helpers
# ---------------------------------------------------------------------------

def _load_session(case_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT id, answers, skipped_fields, prefilled_fields,
                       completed_sections, completion_pct, current_section,
                       current_question_id, consent_record_id,
                       started_at, last_active_at, completed_at
                FROM public.interview_sessions
                WHERE case_id = :case_id AND employee_id = :employee_id
                ORDER BY started_at DESC
                LIMIT 1
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().first()
    return dict(row) if row else None


def _load_session_for_update(case_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
    """Load session with row-level lock (FOR UPDATE) to prevent concurrent corruption."""
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT id, answers, skipped_fields, prefilled_fields,
                       completed_sections, completion_pct, current_section,
                       current_question_id, started_at, last_active_at, completed_at
                FROM public.interview_sessions
                WHERE case_id = :case_id AND employee_id = :employee_id
                ORDER BY started_at DESC
                LIMIT 1
                FOR UPDATE
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().first()
    return dict(row) if row else None


def _load_or_create_session(case_id: str, employee_id: str, org_id: str) -> Dict[str, Any]:
    """Load existing session or create a fresh one."""
    session = _load_session(case_id, employee_id)
    if session:
        return session

    session_id = str(uuid.uuid4())
    now = _now_iso()
    with db.engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO public.interview_sessions
                    (id, case_id, employee_id, org_id,
                     answers, skipped_fields, prefilled_fields, completed_sections,
                     completion_pct, started_at, last_active_at, created_at, updated_at)
                VALUES
                    (:id, :case_id, :employee_id, :org_id,
                     '{}', '{}', '{}', '{}',
                     0, :now, :now, :now, :now)
            """),
            {
                "id": session_id,
                "case_id": case_id,
                "employee_id": employee_id,
                "org_id": org_id,
                "now": now,
            },
        )
    return _load_session(case_id, employee_id) or {}


def _save_session(
    session_id: str,
    answers: Dict[str, Any],
    skipped_fields: List[str],
    prefilled_fields: List[str],
    current_section: Optional[str],
    current_question_id: Optional[str],
    completed_sections: List[str],
    completion_pct: int,
    completed_at: Optional[str],
) -> None:
    import json as _json
    now = _now_iso()
    with db.engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE public.interview_sessions
                SET answers              = :answers,
                    skipped_fields       = :skipped,
                    prefilled_fields     = :prefilled,
                    current_section      = :section,
                    current_question_id  = :question_id,
                    completed_sections   = :completed,
                    completion_pct       = :pct,
                    completed_at         = :completed_at,
                    last_active_at       = :now,
                    updated_at           = :now
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
                "answers": _json.dumps(answers),
                "skipped": skipped_fields,
                "prefilled": prefilled_fields,
                "section": current_section,
                "question_id": current_question_id,
                "completed": completed_sections,
                "pct": completion_pct,
                "completed_at": completed_at,
                "now": now,
            },
        )


def _apply_vault_updates(
    case_id: str,
    employee_id: str,
    vault_updates: Dict[str, Any],
    org_id: str = "",
) -> None:
    """
    Apply a dict of vault column → value updates to imm_employee_profiles.
    Creates the profile row if it doesn't exist.
    Fields already marked 'hr_provided' in field_sources are never overwritten.
    """
    now = _now_iso()
    profile = _load_profile_for_case_employee(case_id, employee_id)

    if profile:
        existing_sources: Dict[str, str] = dict(profile.get("field_sources") or {})
        set_clauses = []
        params: Dict[str, Any] = {"case_id": case_id, "employee_id": employee_id, "now": now}
        for col, val in vault_updates.items():
            if existing_sources.get(col) == "hr_provided":
                continue
            set_clauses.append(f"{col} = :{col}")
            params[col] = val
            existing_sources[col] = "interview"

        if not set_clauses:
            return

        params["field_sources"] = existing_sources
        set_clauses += ["field_sources = :field_sources", "updated_at = :now"]
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE public.imm_employee_profiles "
                    f"SET {', '.join(set_clauses)} "
                    f"WHERE case_id = :case_id AND employee_id = :employee_id"
                ),
                params,
            )
    else:
        profile_id = str(uuid.uuid4())
        field_sources = {col: "interview" for col in vault_updates}
        params = {
            "id": profile_id,
            "case_id": case_id,
            "employee_id": employee_id,
            "org_id": org_id,
            "field_sources": field_sources,
            "created_at": now,
            "updated_at": now,
            **vault_updates,
        }
        cols = list(params.keys())
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO public.imm_employee_profiles ({', '.join(cols)}) "
                    f"VALUES ({', '.join(f':{c}' for c in cols)})"
                ),
                params,
            )


def _get_encryption_key() -> str:
    import os
    key = os.environ.get("IMMIGRATION_ENCRYPTION_KEY", "")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="IMMIGRATION_ENCRYPTION_KEY environment variable not set.",
        )
    return key
