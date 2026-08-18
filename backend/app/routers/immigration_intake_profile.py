"""
immigration_intake_profile.py — employee profile + OCR routes.

Houses 5 endpoints:
  GET   /api/hr/cases/{case_id}/profile                              (HR view, masked)
  PATCH /api/hr/cases/{case_id}/profile/hr-fields                    (HR mutation)
  GET   /api/employee/cases/{case_id}/profile                        (employee read)
  PUT   /api/employee/cases/{case_id}/profile                        (employee upsert)
  POST  /api/employee/cases/{case_id}/profile/ocr-passport           (OCR, async)
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from datetime import date as _date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import (
    get_current_user,
    get_org_id_for_hr_user,
    require_admin_or_hr,
    require_case_access,
)
from ...database import db
from ..db import SessionLocal
from ..services.relocation_plan_view_service import load_profile_draft_for_case
from ..services.nationality_sync import sync_nationality_to_case
from ..services.wizard_draft_mapper import extract_profile_from_wizard_draft
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)
from ..services.immigration_service import (
    _apply_vault_updates,
    _check_consent,
    _get_case_details,
    _get_encryption_key,
    _load_profile_for_case,
    _load_profile_for_case_employee,
    _log_access,
    _now_iso,
    _resolve_canonical_intake_fields,
    decrypt_passport_for_display,
)
from ..services.ocr_passport_extractor import (
    ConflictRecord,
    MrzValidationResult,
    PassportExtractionResult,
    _upload_passport_image,
    detect_conflicts,
    extract_passport,
    validate_mrz,
)


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
    passport_number: Optional[str] = None
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

    # [AIQ-1859] Provenance for THIS write. Not a column — popped before the update is
    # built, so it must never reach the SQL (the handler iterates `updates` as column
    # names). 'ocr_confirmed' is the passport flow: a machine read it, a human checked
    # it. That is a different claim from 'ocr' (machine, unreviewed — what the old
    # auto-save wrote) and from 'self_entered' (typed by hand), and the distinction is
    # the whole point of keeping an audit trail.
    field_source: Optional[str] = None


#: Sources an employee-initiated write may claim. 'hr_provided' is deliberately absent —
#: an employee cannot attribute their own edit to HR.
_EMPLOYEE_FIELD_SOURCES = {"self_entered", "ocr_confirmed"}

router = APIRouter(prefix="/api", tags=["immigration-intake-profile"])

log = logging.getLogger(__name__)


def _jsonb_bind(param: str) -> str:
    """`CAST(:param AS jsonb)` on Postgres; bare `:param` on SQLite (column is TEXT).

    [AIQ-1800b] `field_sources` is jsonb, and every write path bound a raw Python dict to
    it. psycopg2 cannot adapt a dict, so EVERY insert and update against
    imm_employee_profiles raised `ProgrammingError: can't adapt type 'dict'` — which is
    why the table has 0 rows, key or no key. `json.dumps()` on the value is the half that
    actually fixes it; this cast is the house convention (see `_jsonb_expr` in
    admin_form_templates) and keeps the SQLite/Postgres split explicit at the call site.
    """
    try:
        return f"CAST(:{param} AS jsonb)" if db.engine.dialect.name == "postgresql" else f":{param}"
    except Exception:  # engine not configured (unit tests) — bare bind is correct for sqlite
        return f":{param}"


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
        params["field_sources"] = json.dumps(existing_sources)
        set_clauses.append(f"field_sources = {_jsonb_bind('field_sources')}")
        set_clauses.append("updated_at = :now")

        sql = f"""
            UPDATE public.imm_employee_profiles
            SET {', '.join(set_clauses)}
            WHERE case_id = :case_id
            RETURNING id
        """
        with db.engine.begin() as conn:
            conn.execute(text(sql), params)
            try:
                insert_audit_log(
                    conn,
                    entity_type="imm_employee_profile",
                    entity_id=(profile.get("id") or case_id),
                    action_type=ACTION_UPDATE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=hr_user["id"],
                    new_value={"event": "profile_hr_fields_updated", "fields": list(updates.keys())},
                )
            except Exception:
                log.exception("audit: update_profile_hr_fields(update) case=%s", case_id)
    else:
        # No profile yet — create one with just the HR fields
        profile_id = str(uuid.uuid4())
        field_sources = {f: "hr_provided" for f in updates}
        params = {
            "id": profile_id,
            "case_id": case_id,
            "employee_id": "",   # Employee not yet known
            "org_id": org_id,
            "field_sources": json.dumps(field_sources),
            "now": now,
        }
        params.update(updates)
        cols = list(params.keys())
        placeholders = [_jsonb_bind(c) if c == "field_sources" else f":{c}" for c in cols]
        with db.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO public.imm_employee_profiles ({', '.join(cols)})
                    VALUES ({', '.join(placeholders)})
                """),
                params,
            )
            try:
                insert_audit_log(
                    conn,
                    entity_type="imm_employee_profile",
                    entity_id=profile_id,
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=hr_user["id"],
                    new_value={"event": "profile_hr_created", "fields": list(updates.keys())},
                )
            except Exception:
                log.exception("audit: update_profile_hr_fields(create) case=%s", case_id)

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

    # AIQ-973 (ASK-ONCE): canonical intake values the user already gave, surfaced
    # so the profile form pre-fills them to confirm instead of asking again.
    canonical = _resolve_canonical_intake_fields(case_id)

    profile = _load_profile_for_case_employee(case_id, employee_id)
    if not profile:
        # No vault row yet — still surface what intake knows, so it's a confirm,
        # not a blank form. (Empty canonical → genuinely nothing to show.)
        if canonical:
            return {"profile": canonical, "prefilled_from_intake": True}
        return {"profile": None}

    _log_access(
        case_id=case_id,
        profile_id=profile.get("id"),
        user_id=employee_id,
        role="employee",
        action="view",
        fields=["full_profile"],
    )

    # Overlay canonical intake UNDER the real vault: a non-null vault value always
    # wins (OCR'd / already-entered), canonical only fills fields still blank.
    p = dict(canonical)
    for _k, _v in dict(profile).items():
        if _v is not None:
            p[_k] = _v

    # Decrypt passport_number for the employee's own view.
    #
    # [AIQ-1802] Two bugs met here. The overlay above treats any non-null vault value as
    # authoritative, so it had already discarded the employee's own canonical intake
    # value; the decrypt then failed open and returned the ciphertext. Net effect: we
    # showed the employee an unreadable blob while holding the correct plaintext they
    # had typed themselves, a few lines earlier.
    #
    # An undecryptable vault value is not a winning value. Fall back to canonical.
    decryption = decrypt_passport_for_display(p)
    p = decryption.profile
    withheld = decryption.withheld
    if withheld and canonical.get("passport_number"):
        p["passport_number"] = canonical["passport_number"]
        withheld = False

    if withheld:
        return {"profile": p, "passport_number_withheld": True}
    return {"profile": p}


@router.get("/employee/cases/{case_id}/intake-nationality")
def get_intake_nationality_employee(
    case_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """AIQ-1552: the employee's nationality from the intake wizard draft
    (``wizard_cases.draft_json`` → ``employeeProfile.nationality``), to pre-fill
    the Relocation Assistant's nationality selector.

    Reads the wizard draft (NOT ``cases.intake_data``, which drops nationality —
    verified in prod). Deliberately NOT behind the immigration-consent gate that
    guards the PII vault (get_profile_employee): nationality is the employee's own
    intake entry, not vault PII, so the pre-fill must work before/without consent.
    Scoped by require_case_access — the employee may read only their own case
    (cross-employee → 403); HR/admin by company.
    """
    require_case_access(case_id, current_user)
    with SessionLocal() as session:
        draft = load_profile_draft_for_case(session, case_id)
    profile = extract_profile_from_wizard_draft(draft or {})
    return {
        "nationality": profile.get("nationality"),
        "second_nationality": profile.get("second_nationality"),
    }


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
    # [AIQ-1859] Pop before anything reads `updates` as column names — every branch
    # below builds SQL from its keys, so leaving this in would emit `field_source = :…`
    # against a column that does not exist.
    field_source = updates.pop("field_source", None) or "self_entered"
    if field_source not in _EMPLOYEE_FIELD_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=f"field_source must be one of {sorted(_EMPLOYEE_FIELD_SOURCES)}.",
        )
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
                existing_sources[f] = field_source

        set_clauses = []
        params: Dict[str, Any] = {"case_id": case_id, "employee_id": employee_id, "now": now}
        for field_name, value in updates.items():
            if existing_sources.get(field_name) == "hr_provided":
                continue  # HR-locked field — skip
            set_clauses.append(f"{field_name} = :{field_name}")
            params[field_name] = value

        if not set_clauses:
            return {"updated_fields": [], "message": "All fields are HR-provided and locked."}

        params["field_sources"] = json.dumps(existing_sources)
        set_clauses.append(f"field_sources = {_jsonb_bind('field_sources')}")
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
            try:
                insert_audit_log(
                    conn,
                    entity_type="imm_employee_profile",
                    entity_id=(profile.get("id") or case_id),
                    action_type=ACTION_UPDATE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=employee_id,
                    new_value={"event": "profile_self_updated", "fields": list(updates.keys())},
                )
            except Exception:
                log.exception("audit: upsert_profile_employee(update) case=%s", case_id)
    else:
        # Create new profile
        profile_id = str(uuid.uuid4())
        field_sources = {f: field_source for f in updates}
        params = {
            "id": profile_id,
            "case_id": case_id,
            "employee_id": employee_id,
            "org_id": "",
            "field_sources": json.dumps(field_sources),
            "created_at": now,
            "updated_at": now,
        }
        params.update(updates)
        cols = list(params.keys())
        with db.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO public.imm_employee_profiles ({', '.join(cols)})
                    VALUES ({', '.join(_jsonb_bind(c) if c == 'field_sources' else f':{c}' for c in cols)})
                """),
                params,
            )
            try:
                insert_audit_log(
                    conn,
                    entity_type="imm_employee_profile",
                    entity_id=profile_id,
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=employee_id,
                    new_value={"event": "profile_self_created", "fields": list(updates.keys())},
                )
            except Exception:
                log.exception("audit: upsert_profile_employee(create) case=%s", case_id)

    # [AIQ-1880] Confirm is the only point at which a nationality becomes real, so it is
    # the only place worth propagating from. `imm_employee_profiles.nationality` is not
    # what the requirements engine reads — `rules_engine` resolves the class solely from
    # `wizard_cases.draft_json -> employeeProfile.nationality`, so without this the gate
    # stays blind on a case whose passport is already on file and fail-safes to
    # THIRD_COUNTRY without saying so.
    #
    # Deliberately NOT hooked to the OCR endpoint: extraction writes nothing by design
    # (AIQ-1859) and the employee has not agreed to save anything at that point.
    #
    # Best-effort. A profile save that succeeded must not 500 because the mirror failed —
    # the gate degrades to "unknown", which over-shows rather than making a false claim.
    if updates.get("nationality"):
        try:
            with SessionLocal() as _s:
                sync_nationality_to_case(_s, case_id, updates["nationality"])
        except Exception:
            log.exception("nationality_sync: mirror to wizard draft failed case=%s", case_id)

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
    IMM-05 — Passport OCR upload, extract, validate MRZ, detect conflicts.

    Returns extracted fields with per-field confidence, MRZ validation result and
    conflict records. **Extracting does not store anything in the vault.** The
    employee reviews and edits the values, then confirms via
    ``PUT /employee/cases/{case_id}/profile``, which is the only write path.

    [AIQ-1859] This used to call ``save_ocr_to_vault`` right here, before the
    employee had seen a single field — the docstring said so plainly: "Does NOT
    require the employee to confirm — fields are saved immediately". The UI's
    "Save extracted data" button was therefore decorative, and its "Discard & enter
    manually" only advanced the wizard (ImmigrationPage sets stage='interview') while
    the passport number, MRZ lines and date of birth stayed in the vault. With the
    vault key live that is passport data written before the person agreed to save it,
    and declining did not remove it.

    The uploaded image is still stored — that is the document of record and is
    governed by consent above. Only the extracted *field* write moved.
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

    # --- NO vault write here ---
    # [AIQ-1859] `save_ocr_to_vault(...)` used to run at this point. It does not any
    # more: the employee confirms first, and PUT /employee/cases/{id}/profile performs
    # the write. Do not reinstate a write here — a test asserts this endpoint performs
    # none (backend/tests/test_ocr_passport_no_write_before_confirm.py).
    profile_id = existing_profile.get("id") if existing_profile else None

    # --- Log access ---
    # These are the fields the extraction READ off the passport, not fields written.
    # The action name says so: an `ocr_extract` that persisted nothing must not leave
    # an audit trail implying it did.
    extracted_fields_present = [
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
        profile_id=profile_id,
        user_id=employee_id,
        role="employee",
        action="ocr_extract_preview",
        fields=extracted_fields_present,
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


