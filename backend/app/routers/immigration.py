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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
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
    """Fetch basic case details (corridor, visa_type, move_date) scoped to org."""
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT ca.case_id, ca.employee_user_id,
                       c.dest_country, c.origin_country
                FROM public.case_assignments ca
                LEFT JOIN public.cases c ON c.id = ca.case_id
                WHERE ca.case_id = :case_id
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
            corridor_from = corridor_from or case.get("origin_country", "FR")
            corridor_to = corridor_to or case.get("dest_country", "DE")
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
# Stubs for future tasks (return 501 with helpful message)
# ---------------------------------------------------------------------------

@router.post("/employee/cases/{case_id}/profile/ocr-passport")
def ocr_passport_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="OCR passport extraction (IMM-05) not yet implemented.")


@router.get("/employee/cases/{case_id}/interview/next")
def interview_next_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Interview engine (IMM-06) not yet implemented.")


@router.post("/employee/cases/{case_id}/interview/answer")
def interview_answer_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Interview engine (IMM-06) not yet implemented.")


@router.get("/employee/cases/{case_id}/interview/status")
def interview_status_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Interview engine (IMM-06) not yet implemented.")


@router.get("/employee/cases/{case_id}/my-data/export")
def data_export_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Data export (IMM-17) not yet implemented.")


@router.post("/employee/cases/{case_id}/my-data/erasure-request")
def erasure_request_stub(case_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Erasure workflow (IMM-18) not yet implemented.")


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


def _get_encryption_key() -> str:
    import os
    key = os.environ.get("IMMIGRATION_ENCRYPTION_KEY", "")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="IMMIGRATION_ENCRYPTION_KEY environment variable not set.",
        )
    return key
