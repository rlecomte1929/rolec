"""
OCR Passport Extractor — IMM-05
================================
Extracts structured data from a passport photo using GPT-4o vision,
validates the MRZ using the ICAO 9303 checksum algorithm (implemented
from scratch), detects conflicts with existing vault data, and optionally
auto-saves the extracted fields to imm_employee_profiles.

Public API
----------
  extract_passport(image_bytes)              -> PassportExtractionResult
  validate_mrz(mrz_line1, mrz_line2)         -> MrzValidationResult
  detect_conflicts(extraction, vault_fields) -> List[ConflictRecord]
  save_ocr_to_vault(case_id, employee_id, extraction, org_id) -> str
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PassportExtractionResult:
    # Identity fields
    surname: Optional[str] = None
    given_names: Optional[str] = None
    date_of_birth: Optional[str] = None          # YYYY-MM-DD
    gender: Optional[str] = None                 # M / F / X
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None            # ISO 3-letter code
    issuing_country: Optional[str] = None        # ISO 3-letter code

    # Passport fields
    passport_number: Optional[str] = None
    issue_date: Optional[str] = None             # YYYY-MM-DD
    expiry_date: Optional[str] = None            # YYYY-MM-DD

    # MRZ raw
    mrz_line1: Optional[str] = None
    mrz_line2: Optional[str] = None

    # Per-field confidence (0.0–1.0)
    confidence: Dict[str, float] = field(default_factory=dict)

    # Overall extraction quality flag
    low_quality: bool = False
    low_quality_reason: Optional[str] = None


class OcrExtractionError(Exception):
    """
    Raised when passport extraction fails for a known, user-facing reason.
    Carries a machine-readable code, a user-friendly message, and an optional hint.
    """
    def __init__(self, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


@dataclass
class MrzValidationResult:
    is_valid: bool
    error_fields: List[str] = field(default_factory=list)   # field names that failed checksum
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictRecord:
    field_name: str
    ocr_value: str
    vault_value: str
    vault_source: str   # 'self_entered' | 'hr_provided' | 'ocr'


# ---------------------------------------------------------------------------
# ICAO 9303 MRZ checksum (implemented from scratch)
# ---------------------------------------------------------------------------

_MRZ_CHAR_VALUES: Dict[str, int] = {
    **{str(i): i for i in range(10)},
    **{chr(65 + i): 10 + i for i in range(26)},
    "<": 0,
}
_MRZ_WEIGHTS = [7, 3, 1]


def _icao_check_digit(chars: str) -> int:
    """Compute the ICAO 9303 check digit for a string of MRZ characters."""
    total = 0
    for i, c in enumerate(chars.upper()):
        total += _MRZ_CHAR_VALUES.get(c, 0) * _MRZ_WEIGHTS[i % 3]
    return total % 10


def validate_mrz(mrz_line1: str, mrz_line2: str) -> MrzValidationResult:
    """
    Validate a TD3 (standard 44-char) passport MRZ against ICAO 9303 checksums.

    TD3 line 2 layout (44 chars):
      [0:9]  document number
      [9]    check digit — document number
      [10:13] nationality
      [13:19] DOB (YYMMDD)
      [19]   check digit — DOB
      [20]   sex
      [21:27] expiry (YYMMDD)
      [27]   check digit — expiry
      [28:42] personal number / filler
      [42]   check digit — personal number (0 if empty)
      [43]   composite check digit (covers l2[0:10]+l2[13:20]+l2[21:43])
    """
    l1 = mrz_line1.upper().replace(" ", "")
    l2 = mrz_line2.upper().replace(" ", "")

    errors: List[str] = []
    details: Dict[str, Any] = {}

    if len(l2) != 44:
        return MrzValidationResult(
            is_valid=False,
            error_fields=["mrz_line2_length"],
            details={"expected": 44, "got": len(l2)},
        )

    # 1. Document number check digit (position 9)
    doc_number = l2[0:9]
    expected_doc_cd = int(l2[9]) if l2[9].isdigit() else -1
    computed_doc_cd = _icao_check_digit(doc_number)
    details["document_number_check"] = {
        "computed": computed_doc_cd, "stored": l2[9], "pass": computed_doc_cd == expected_doc_cd
    }
    if computed_doc_cd != expected_doc_cd:
        errors.append("passport_number")

    # 2. DOB check digit (position 19)
    dob = l2[13:19]
    expected_dob_cd = int(l2[19]) if l2[19].isdigit() else -1
    computed_dob_cd = _icao_check_digit(dob)
    details["dob_check"] = {
        "computed": computed_dob_cd, "stored": l2[19], "pass": computed_dob_cd == expected_dob_cd
    }
    if computed_dob_cd != expected_dob_cd:
        errors.append("date_of_birth")

    # 3. Expiry date check digit (position 27)
    expiry = l2[21:27]
    expected_exp_cd = int(l2[27]) if l2[27].isdigit() else -1
    computed_exp_cd = _icao_check_digit(expiry)
    details["expiry_check"] = {
        "computed": computed_exp_cd, "stored": l2[27], "pass": computed_exp_cd == expected_exp_cd
    }
    if computed_exp_cd != expected_exp_cd:
        errors.append("expiry_date")

    # 4. Personal number check digit (position 42) — 0 is valid when field is all filler
    personal = l2[28:42]
    expected_pn_cd = int(l2[42]) if l2[42].isdigit() else -1
    computed_pn_cd = _icao_check_digit(personal)
    details["personal_number_check"] = {
        "computed": computed_pn_cd, "stored": l2[42], "pass": computed_pn_cd == expected_pn_cd
    }
    if computed_pn_cd != expected_pn_cd:
        errors.append("personal_number")

    # 5. Composite check digit (position 43)
    # Covers: l2[0:10] + l2[13:20] + l2[21:43]
    composite_input = l2[0:10] + l2[13:20] + l2[21:43]
    expected_comp_cd = int(l2[43]) if l2[43].isdigit() else -1
    computed_comp_cd = _icao_check_digit(composite_input)
    details["composite_check"] = {
        "computed": computed_comp_cd, "stored": l2[43], "pass": computed_comp_cd == expected_comp_cd
    }
    if computed_comp_cd != expected_comp_cd:
        errors.append("mrz_composite")

    return MrzValidationResult(
        is_valid=len(errors) == 0,
        error_fields=errors,
        details=details,
    )


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

# Maps OCR field names → vault column names
_FIELD_MAPPING = {
    "surname": "legal_last_name",
    "given_names": "legal_first_name",
    "date_of_birth": "date_of_birth",
    "nationality": "nationality",
    "passport_number": "passport_number",
    "expiry_date": "passport_expiry",
    "issue_date": "passport_issue_date",
    "issuing_country": "passport_country",
    "mrz_line1": "passport_mrz_line1",
    "mrz_line2": "passport_mrz_line2",
    "gender": "gender",
    "place_of_birth": "place_of_birth",
}


def detect_conflicts(
    extraction: PassportExtractionResult,
    vault_fields: Dict[str, Any],
    field_sources: Optional[Dict[str, str]] = None,
) -> List[ConflictRecord]:
    """
    Compare extracted fields against what's already in the vault.
    Returns a ConflictRecord for each field that differs.
    vault_fields: flat dict of vault column name → current value.
    field_sources: dict of column name → source ('self_entered'|'hr_provided'|'ocr')
    """
    conflicts: List[ConflictRecord] = []
    sources = field_sources or {}

    for ocr_field, vault_col in _FIELD_MAPPING.items():
        ocr_val = getattr(extraction, ocr_field, None)
        vault_val = vault_fields.get(vault_col)

        if not ocr_val or not vault_val:
            continue

        # Normalise for comparison
        ocr_norm = str(ocr_val).strip().upper()
        vault_norm = str(vault_val).strip().upper()

        # Skip encrypted passport_number blobs (they won't match plain text)
        if vault_col == "passport_number" and len(vault_val) > 50:
            continue

        if ocr_norm != vault_norm:
            conflicts.append(ConflictRecord(
                field_name=ocr_field,
                ocr_value=str(ocr_val),
                vault_value=str(vault_val),
                vault_source=sources.get(vault_col, "unknown"),
            ))

    return conflicts


# ---------------------------------------------------------------------------
# GPT-4o Vision extraction
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
You are a passport OCR specialist. Extract all fields from the passport image.
Return ONLY valid JSON matching this exact schema — no markdown, no explanation:

{
  "surname": "SMITH",
  "given_names": "JOHN MICHAEL",
  "date_of_birth": "1985-03-15",
  "gender": "M",
  "place_of_birth": "LONDON",
  "nationality": "GBR",
  "issuing_country": "GBR",
  "passport_number": "AB1234567",
  "issue_date": "2020-01-10",
  "expiry_date": "2030-01-09",
  "mrz_line1": "P<GBRSMITH<<JOHN<MICHAEL<<<<<<<<<<<<<<<<<<<<<",
  "mrz_line2": "AB12345671GBR8503155M3001094<<<<<<<<<<<<<<<6",
  "confidence": {
    "surname": 0.99,
    "given_names": 0.98,
    "date_of_birth": 0.97,
    "gender": 0.99,
    "place_of_birth": 0.85,
    "nationality": 0.99,
    "issuing_country": 0.99,
    "passport_number": 0.99,
    "issue_date": 0.95,
    "expiry_date": 0.99,
    "mrz_line1": 0.95,
    "mrz_line2": 0.95
  },
  "error_type": null,
  "error_detail": null
}

Rules:
- Dates must be in YYYY-MM-DD format.
- nationality and issuing_country must be ISO 3-letter codes (e.g. GBR, FRA, DEU).
  For non-standard or unrecognised country codes (e.g. RSL, XKX), use your best guess at the
  ISO 3166-1 alpha-3 equivalent or keep as-is — do NOT set error_type for this alone.
- For any field you cannot read clearly, set value to null and confidence to 0.0.
- MRZ lines must be exactly 44 uppercase characters (pad with < if needed).
- If no MRZ is visible at all (e.g. older passport without machine-readable zone), set
  mrz_line1 and mrz_line2 to null and set "error_type": "no_mrz".
- If the image is not a passport at all, set all fields to null and set "error_type": "not_a_passport".
- If the document has the word "SPECIMEN", "SAMPLE", or "SPÉCIMEN" printed on it, set
  "error_type": "specimen_document".
- If image quality prevents reliable extraction (blurry, too dark, cropped), set
  "low_quality": true, "error_type": "low_quality", and "error_detail": "<short reason>".
- If the passport is partially visible or cut off, set "error_type": "partial_image".
- error_type must be one of: null | "no_mrz" | "not_a_passport" | "specimen_document" |
  "low_quality" | "partial_image".
- IMPORTANT: A "no_mrz" error does NOT prevent extraction of all other fields. Continue to
  extract all visible text fields normally even if no MRZ is present.
"""

_MIN_CONFIDENCE = 0.70   # Below this, fields are treated as unreadable
_CRITICAL_FIELDS = {"surname", "given_names", "date_of_birth", "passport_number", "expiry_date"}
_CRITICAL_MIN_CONFIDENCE = 0.90


async def extract_passport(image_bytes: bytes, mime_type: str = "image/jpeg") -> PassportExtractionResult:
    """
    Send the passport image to GPT-4o vision and return a PassportExtractionResult.
    Raises ValueError for low-quality or non-passport images.

    Uses llm_client.complete() for timeout, retry, and structured logging.
    """
    from .llm_client import complete as llm_complete  # local import avoids circular dep

    # Encode image as base64 data URL
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    # Call GPT-4o vision via the shared wrapper.
    # We pass an empty schema so the wrapper uses json_object mode (free-form JSON),
    # which is required here because the response includes dynamic "confidence" keys.
    data = await llm_complete(
        system="",
        user=_EXTRACTION_PROMPT,
        schema={},
        image_url=data_url,
        timeout=45.0,       # vision calls are slower; allow extra time
        max_retries=2,
        model="gpt-4o",
    )

    # --- Map error_type to specific, user-facing OcrExtractionError ---
    error_type = data.get("error_type")

    if error_type == "not_a_passport" or data.get("not_a_passport"):
        raise OcrExtractionError(
            code="not_a_passport",
            message="This doesn't look like a passport data page.",
            hint="Please upload a photo of the biographical page — the one with your photo and "
                 "personal details. Make sure the full page is visible.",
        )

    if error_type == "specimen_document":
        raise OcrExtractionError(
            code="specimen_document",
            message="This appears to be a specimen or sample passport.",
            hint="Specimen documents cannot be processed. Please upload your actual passport.",
        )

    if error_type == "partial_image":
        raise OcrExtractionError(
            code="partial_image",
            message="The passport page isn't fully visible in the photo.",
            hint="Make sure the entire biographical page fits within the frame — "
                 "include all four corners and the MRZ lines at the bottom.",
        )

    if error_type == "low_quality":
        detail = data.get("error_detail", "")
        hint_parts = [
            "Retake the photo in good lighting.",
            "Lay the passport flat and hold the camera directly above it.",
            "Make sure the text is sharp and there's no glare.",
        ]
        raise OcrExtractionError(
            code="low_quality",
            message=f"The image quality is too low to read the passport reliably.{' (' + detail + ')' if detail else ''}",
            hint=" ".join(hint_parts),
        )

    confidence = data.get("confidence", {})

    result = PassportExtractionResult(
        surname=data.get("surname"),
        given_names=data.get("given_names"),
        date_of_birth=_normalise_date(data.get("date_of_birth")),
        gender=data.get("gender"),
        place_of_birth=data.get("place_of_birth"),
        nationality=data.get("nationality"),
        issuing_country=data.get("issuing_country"),
        passport_number=data.get("passport_number"),
        issue_date=_normalise_date(data.get("issue_date")),
        expiry_date=_normalise_date(data.get("expiry_date")),
        mrz_line1=data.get("mrz_line1"),
        mrz_line2=data.get("mrz_line2"),
        confidence=confidence,
        low_quality=bool(data.get("low_quality", False)),
        low_quality_reason=data.get("low_quality_reason"),
    )

    # Zero out fields below minimum confidence threshold
    for f in list(_FIELD_MAPPING.keys()):
        if confidence.get(f, 1.0) < _MIN_CONFIDENCE:
            setattr(result, f, None)

    # Reject if any critical field is below the higher critical threshold
    critical_failures = [
        f for f in _CRITICAL_FIELDS
        if confidence.get(f, 0.0) < _CRITICAL_MIN_CONFIDENCE and getattr(result, f) is None
    ]
    if critical_failures or result.low_quality:
        # "no_mrz" is a soft warning — don't block if other fields were extracted
        if error_type == "no_mrz" and not critical_failures:
            pass  # Allow through — MRZ-less passports are valid (older formats)
        else:
            reason = result.low_quality_reason or ", ".join(critical_failures)
            raise OcrExtractionError(
                code="low_confidence",
                message="We couldn't read some required fields from this passport.",
                hint=f"Fields that couldn't be read clearly: {reason}. "
                     "Try uploading a clearer photo, or skip this step and enter your details manually.",
            )

    return result


def _normalise_date(val: Optional[str]) -> Optional[str]:
    """Attempt to coerce various date formats to YYYY-MM-DD. Returns None on failure."""
    if not val:
        return None
    val = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return val  # Return as-is if nothing matched — GPT usually follows the prompt


# ---------------------------------------------------------------------------
# Supabase Storage upload
# ---------------------------------------------------------------------------

def _upload_passport_image(case_id: str, image_bytes: bytes, mime_type: str) -> Optional[str]:
    """
    Upload the passport image to Supabase Storage (private bucket 'immigration').
    Path: immigration/{case_id}/passport_page.jpg
    Returns the storage path, or None if upload fails (non-blocking).
    """
    try:
        from ..services.supabase_client import get_supabase_admin_client  # type: ignore
        # supabase_client is at backend/services/ (legacy path), try both
    except ImportError:
        try:
            import sys, os as _os
            _backend = _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__)))
            sys.path.insert(0, _backend)
            from services.supabase_client import get_supabase_admin_client  # type: ignore
        except ImportError:
            log.warning("Supabase client not available — skipping storage upload.")
            return None

    ext = "jpg" if "jpeg" in mime_type else mime_type.split("/")[-1]
    storage_path = f"immigration/{case_id}/passport_page.{ext}"

    try:
        admin = get_supabase_admin_client()
        admin.storage.from_("immigration").upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": mime_type, "upsert": "true"},
        )
        log.info("Passport image uploaded to storage: %s", storage_path)
        return storage_path
    except Exception as exc:
        log.warning("Passport image upload failed (non-blocking): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Auto-save extracted fields to vault (imm_employee_profiles)
# ---------------------------------------------------------------------------

def save_ocr_to_vault(
    case_id: str,
    employee_id: str,
    extraction: PassportExtractionResult,
    org_id: str = "",
) -> str:
    """
    Upsert extracted passport fields into imm_employee_profiles.
    Fields with source 'hr_provided' are never overwritten.
    Returns the profile id (existing or newly created).
    """
    from sqlalchemy import text as _text
    from ...database import db

    # Build vault update dict from extraction
    raw_updates: Dict[str, Any] = {}
    if extraction.surname:
        raw_updates["legal_last_name"] = extraction.surname.title()
    if extraction.given_names:
        raw_updates["legal_first_name"] = extraction.given_names.title()
    if extraction.date_of_birth:
        raw_updates["date_of_birth"] = extraction.date_of_birth
    if extraction.gender:
        raw_updates["gender"] = extraction.gender
    if extraction.place_of_birth:
        raw_updates["place_of_birth"] = extraction.place_of_birth
    if extraction.nationality:
        raw_updates["nationality"] = extraction.nationality
    if extraction.issuing_country:
        raw_updates["passport_country"] = extraction.issuing_country
    if extraction.expiry_date:
        raw_updates["passport_expiry"] = extraction.expiry_date
    if extraction.issue_date:
        raw_updates["passport_issue_date"] = extraction.issue_date
    if extraction.mrz_line1:
        raw_updates["passport_mrz_line1"] = extraction.mrz_line1
    if extraction.mrz_line2:
        raw_updates["passport_mrz_line2"] = extraction.mrz_line2

    if not raw_updates and not extraction.passport_number:
        return ""

    now = datetime.now(timezone.utc).isoformat()

    # Load existing profile
    with db.engine.begin() as conn:
        row = conn.execute(
            _text("""
                SELECT id, field_sources FROM public.imm_employee_profiles
                WHERE case_id = :case_id AND employee_id = :employee_id
                LIMIT 1
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().first()

    if row:
        profile_id = row["id"]
        existing_sources: Dict[str, str] = dict(row["field_sources"] or {})

        # Encrypt passport_number via pgcrypto if provided. Fails closed —
        # never writes the plaintext when encryption is unavailable.
        if extraction.passport_number:
            raw_updates["passport_number"] = _encrypt_passport_number(
                extraction.passport_number
            )

        # Build SET clauses, skipping hr_provided fields
        set_clauses = []
        params: Dict[str, Any] = {"case_id": case_id, "employee_id": employee_id, "now": now}
        for col, val in raw_updates.items():
            if existing_sources.get(col) == "hr_provided":
                continue
            set_clauses.append(f"{col} = :{col}")
            params[col] = val
            existing_sources[col] = "ocr"

        if not set_clauses:
            return profile_id

        params["field_sources"] = existing_sources
        set_clauses += ["field_sources = :field_sources", "updated_at = :now"]

        with db.engine.begin() as conn:
            conn.execute(
                _text(
                    f"UPDATE public.imm_employee_profiles "
                    f"SET {', '.join(set_clauses)} "
                    f"WHERE case_id = :case_id AND employee_id = :employee_id"
                ),
                params,
            )
    else:
        # Create new profile
        profile_id = str(uuid.uuid4())

        if extraction.passport_number:
            raw_updates["passport_number"] = _encrypt_passport_number(
                extraction.passport_number
            )

        field_sources = {col: "ocr" for col in raw_updates}
        params = {
            "id": profile_id,
            "case_id": case_id,
            "employee_id": employee_id,
            "org_id": org_id,
            "field_sources": field_sources,
            "created_at": now,
            "updated_at": now,
            **raw_updates,
        }
        cols = list(params.keys())
        with db.engine.begin() as conn:
            conn.execute(
                _text(
                    f"INSERT INTO public.imm_employee_profiles ({', '.join(cols)}) "
                    f"VALUES ({', '.join(f':{c}' for c in cols)})"
                ),
                params,
            )

    return profile_id


def _get_enc_key() -> Optional[str]:
    key = os.environ.get("IMMIGRATION_ENCRYPTION_KEY", "")
    return key if key else None


def _encrypt_passport_number(value: str) -> Any:
    """Encrypt a passport number for vault storage, or raise. **Fails closed.**

    [AIQ-1780] Both call sites in ``save_ocr_to_vault`` previously did::

        enc_key = _get_enc_key()
        if enc_key:                 # unset key -> silently skipped
            ...encrypt...
        # raw_updates["passport_number"] keeps the PLAINTEXT and is written

    With ``IMMIGRATION_ENCRYPTION_KEY`` unset — which is the case in production —
    that wrote a passport number to the database in the clear. It is an Article 9
    special-category identifier; storing it unencrypted because a config value is
    missing is the worst possible response to that condition.

    Its sibling on the manual-update path already fails closed
    (``immigration_intake_profile.update_profile_employee`` raises 500 rather than
    write). The two paths disagreeing is the actual defect; this makes them agree.

    Raising costs the rest of the OCR result for this request, which is the right
    trade: the extraction is re-runnable from the same image, whereas a plaintext
    passport number in the database is not un-leaked. The caller only reaches this
    when a passport number was actually read, so OCR results without one still save.

    Returns the pgcrypto ciphertext. Never returns, logs, or falls back to plaintext.
    """
    from sqlalchemy import text as _text

    from ...database import db

    key = _get_enc_key()
    if not key:
        raise HTTPException(
            status_code=500,
            detail="Cannot store passport number securely: encryption is not configured.",
        )

    with db.engine.begin() as conn:
        row = conn.execute(
            _text("SELECT pgp_sym_encrypt(:val, :key) AS encrypted"),
            {"val": value, "key": key},
        ).mappings().first()

    encrypted = row["encrypted"] if row else None
    if encrypted is None:
        # Do NOT fall through to the plaintext value.
        raise HTTPException(status_code=500, detail="Failed to encrypt sensitive data.")
    return encrypted
