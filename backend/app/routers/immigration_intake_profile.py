"""
immigration_intake_profile.py — employee profile + OCR routes
extracted from immigration.py (AUDIT-B9-imm-3, part 2 of 3).

Houses 5 endpoints:
  GET   /api/hr/cases/{case_id}/profile                              (HR view, masked)
  PATCH /api/hr/cases/{case_id}/profile/hr-fields                    (HR mutation)
  GET   /api/employee/cases/{case_id}/profile                        (employee read)
  PUT   /api/employee/cases/{case_id}/profile                        (employee upsert)
  POST  /api/employee/cases/{case_id}/profile/ocr-passport           (OCR, async)

DORMANT: this router is not yet wired into backend/app/main.py.
Canonical registration still happens via immigration.py until imm-6.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from datetime import date as _date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user, get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.immigration_service import (
    _apply_vault_updates,
    _check_consent,
    _get_case_details,
    _get_encryption_key,
    _load_profile_for_case,
    _load_profile_for_case_employee,
    _log_access,
    _now_iso,
)
from ..services.ocr_passport_extractor import (
    ConflictRecord,
    MrzValidationResult,
    PassportExtractionResult,
    _upload_passport_image,
    detect_conflicts,
    extract_passport,
    save_ocr_to_vault,
    validate_mrz,
)

# Pydantic models — imported from immigration.py until imm-6 relocates them.
from .immigration import EmployeeProfileUpdate, HrProfileFields

router = APIRouter(prefix="/api", tags=["immigration-intake-profile"])


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

    # --- Validate file type and size (SEC-006: server-side, content-based) ---
    # MIME is sniffed from the bytes via libmagic, never the client header.
    # 415 on disallowed type, 413 on oversize. Images only (JPEG/PNG/WebP).
    from ..services.upload_validator import ALLOWED_IMAGE_MIME, read_and_validate

    image_bytes, _safe_name, content_type = await read_and_validate(
        passport_image,
        allowed_mime=ALLOWED_IMAGE_MIME,
        max_bytes=10 * 1024 * 1024,  # passport photos: 10 MiB
    )

    # --- Upload to Supabase Storage (non-blocking) ---
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


# ---------------------------------------------------------------------------
# HR: PATCH /api/hr/cases/{case_id}/expected-start-date  (Phase B1)
# ---------------------------------------------------------------------------


class ExpectedStartDateBody(BaseModel):
    expected_start_date: _date  # Pydantic parses ISO YYYY-MM-DD; rejects others.


@router.patch("/hr/cases/{case_id}/expected-start-date")
def update_case_expected_start_date(
    case_id: str,
    body: ExpectedStartDateBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """HR sets the case's expected start date. Feeds the BL-Compliance
    `tax_183_day` rule via the `days_present_in_host` derivation."""
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "UPDATE public.relocation_cases "
                "SET expected_start_date = :d, updated_at = now() "
                "WHERE id = :case_id AND company_id = :company_id "
                "RETURNING id"
            ),
            {"d": body.expected_start_date, "case_id": case_id, "company_id": org_id},
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found or not in your company")
    return {
        "case_id": case_id,
        "expected_start_date": body.expected_start_date.isoformat(),
    }


