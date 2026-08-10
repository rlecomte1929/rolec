"""
immigration_forms.py — IMM-11

HR-facing immigration form pre-fill endpoints.

  GET  /api/hr/cases/{case_id}/immigration/available-forms
  POST /api/hr/cases/{case_id}/immigration/generate-form   body {form_id}

generate-form loads the case's immigration vault profile, decrypts the passport
number, fills the requested AcroForm template, stores the result in Supabase
Storage and returns a time-limited download URL plus a per-field fill report.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.form_prefill_service import (
    generate_prefilled_pdf,
    get_available_forms,
    visa_types_for_corridor,
)
from ..services.immigration_service import (
    _get_case_details,
    _get_encryption_key,
    _load_profile_for_case,
    _log_access,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["immigration-forms"])


class GenerateFormBody(BaseModel):
    form_id: str


def _decrypt_passport(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the profile with passport_number decrypted for pre-fill."""
    p = dict(profile)
    if p.get("passport_number"):
        try:
            enc_key = _get_encryption_key()
            with db.engine.begin() as conn:
                row = conn.execute(
                    text("SELECT pgp_sym_decrypt(CAST(:enc AS bytea), :key) AS decrypted"),
                    {"enc": p["passport_number"], "key": enc_key},
                ).mappings().first()
            if row:
                p["passport_number"] = row["decrypted"]
        except Exception:
            # Leave the encrypted form rather than fail the whole fill.
            log.warning("passport decryption failed during form pre-fill")
    return p


@router.get("/hr/cases/{case_id}/immigration/available-forms")
def list_available_forms(
    case_id: str,
    visa_type: Optional[str] = None,
    corridor_to: Optional[str] = None,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Forms available for pre-fill for this case's corridor/visa combination.

    [AIQ-1771] Both inputs are resolved from the case, never defaulted. The
    previous signature defaulted `visa_type="blue_card"` and fell back to
    `corridor_to="DE"`, which produced two distinct wrong answers:

      * a FR case queried FR+blue_card, matched nothing, and showed NO forms —
        the feature simply looked absent;
      * a case with no `dest_country` became a German case and was offered the
        Blue Card — a wrong form presented as correct.

    Now: no corridor -> 422 rather than a guess; visa type derived from what the
    corridor actually has. A corridor with no fillable forms returns an empty
    list, which is the right answer for portal/data-sheet corridors like Norway
    (FINDINGS.md Appendix A.1) rather than an error.
    """
    if not corridor_to:
        case = _get_case_details(case_id, org_id)
        corridor_to = (case.get("dest_country") if case else None) or None

    if not corridor_to:
        # Fail closed. Guessing here is what offered a German form to a case with
        # no destination at all.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Cannot determine the destination corridor for this case. "
                "Set the case's destination country, or pass ?corridor_to=XX."
            ),
        )

    if not visa_type:
        candidates = visa_types_for_corridor(corridor_to)
        if len(candidates) == 1:
            visa_type = candidates[0]
        elif len(candidates) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Corridor {corridor_to} has more than one visa type with "
                    f"mapped forms ({', '.join(candidates)}); pass ?visa_type= "
                    "to choose."
                ),
            )
        else:
            # No fillable forms for this corridor — correct for data-sheet
            # corridors. Echo the corridor so the caller can say so plainly.
            return {"corridor_to": corridor_to, "visa_type": None, "forms": []}

    forms = get_available_forms(corridor_to, visa_type)
    return {
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "forms": [f.to_dict() for f in forms],
    }


@router.post("/hr/cases/{case_id}/immigration/generate-form")
def generate_form(
    case_id: str,
    body: GenerateFormBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Generate a pre-filled PDF for `form_id` from the case's vault profile."""
    profile = _load_profile_for_case(case_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No immigration profile found for this case.",
        )

    profile = _decrypt_passport(profile)

    try:
        result = generate_prefilled_pdf(body.form_id, case_id, profile)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    _log_access(
        case_id=case_id,
        profile_id=profile.get("id"),
        user_id=hr_user["id"],
        role="hr",
        action="form_prefill",
        fields=[body.form_id],
    )

    return {
        "download_url": result.download_url,
        "fill_report": result.to_dict(),
    }
