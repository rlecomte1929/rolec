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

from ..auth_deps import (
    get_org_id_for_hr_user,
    require_admin_or_hr,
    require_case_access,
    require_hr_or_employee,
)
from ...database import db
from ..services.form_prefill_service import (
    FILLABLE_FORM_IDS,
    generate_prefilled_pdf,
    get_available_forms,
    visa_types_for_corridor,
)
from ..services.immigration_service import (
    _check_consent,
    _get_case_details,
    _load_profile_for_case,
    _load_profile_for_case_employee,
    _log_access,
    decrypt_passport_for_display,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["immigration-forms"])


class GenerateFormBody(BaseModel):
    form_id: str


def _decrypt_passport(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the profile with passport_number decrypted for pre-fill.

    [AIQ-1802] On failure the field is left BLANK, not filled with the ciphertext. This
    used to "leave the encrypted form rather than fail the whole fill", which meant an
    unreadable blob could be pre-filled onto an official immigration application. A blank
    field the applicant completes themselves is strictly better than a wrong one they
    might not notice.
    """
    result = decrypt_passport_for_display(profile)
    if result.withheld:
        log.warning("passport decryption failed during form pre-fill; field left blank")
    return result.profile


def _forms_payload(corridor_to: Optional[str], visa_type: Optional[str]) -> Dict[str, Any]:
    """Resolve the fillable forms for a corridor/visa pair.

    [AIQ-1855] Shared by the HR and employee available-forms routes so both fail the
    same way. Fail-closed: no corridor -> 422 (never a DE default, per AIQ-1771); a
    corridor with more than one form-bearing visa -> 422 asking the caller to choose;
    a corridor with no fillable forms -> an empty list, which is the right answer for
    portal/data-sheet corridors like Norway rather than an error.
    """
    if not corridor_to:
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
            return {"corridor_to": corridor_to, "visa_type": None, "forms": []}
    forms = get_available_forms(corridor_to, visa_type)
    return {
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "forms": [f.to_dict() for f in forms],
    }


def _generate_and_report(
    case_id: str,
    profile: Dict[str, Any],
    form_id: str,
    user_id: str,
    role: str,
) -> Dict[str, Any]:
    """Decrypt the passport, pre-fill the PDF, log the access, and return the signed
    download URL + per-field fill report. [AIQ-1855] Shared by the HR and employee
    generate-form routes; the caller is responsible for loading a profile the caller
    is authorised to read (HR: org-scoped; employee: their own case + consent)."""
    # Defense in depth: get_available_forms already hides non-fillable forms, but a direct
    # POST could still name one. Only genuinely-fillable government AcroForms may be
    # generated — never a synthetic stand-in (e.g. DE_blue_card_v2024, which has no real PDF).
    if form_id not in FILLABLE_FORM_IDS:
        raise HTTPException(status_code=404, detail="form not available")
    profile = _decrypt_passport(profile)
    try:
        result = generate_prefilled_pdf(form_id, case_id, profile)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    _log_access(
        case_id=case_id,
        profile_id=profile.get("id"),
        user_id=user_id,
        role=role,
        action="form_prefill",
        fields=[form_id],
    )
    return {"download_url": result.download_url, "fill_report": result.to_dict()}


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
    return _forms_payload(corridor_to, visa_type)


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
    return _generate_and_report(case_id, profile, body.form_id, hr_user["id"], "hr")


# ─────────────────────────────────────────────────────────────────────────────
# [AIQ-1855] Employee-facing pre-fill — the relocating employee reaches the same
# forms for their OWN case. The HR routes above are require_admin_or_hr; these are
# require_hr_or_employee + require_case_access, so the path case_id is authorised
# (employee owns the assignment, or HR has visibility) BEFORE anything is read —
# fail-closed on cross-case access, mirroring employee_immigration_snapshot.
#
# available-forms reads no vault, so ownership is the only gate; generate-form
# reads + decrypts the caller's OWN profile (scoped by (case_id, employee_id)) and
# only behind the immigration consent gate, matching the employee profile-read
# route. corridor_to is supplied by the employee dossier (which already holds the
# case destination); absent, it fails closed with 422 rather than guessing.
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/employee/cases/{case_id}/immigration/available-forms")
def list_available_forms_employee(
    case_id: str,
    visa_type: Optional[str] = None,
    corridor_to: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """Forms available for pre-fill for the caller's OWN case. Ownership-gated."""
    require_case_access(case_id, user)  # 403/404 before anything is resolved
    if not corridor_to:
        # org_id is unused by _get_case_details' query; ownership is already enforced
        # by require_case_access above (same pattern as immigration_snapshot_service).
        case = _get_case_details(case_id, "")
        corridor_to = (case.get("dest_country") if case else None) or None
    return _forms_payload(corridor_to, visa_type)


@router.post("/employee/cases/{case_id}/immigration/generate-form")
def generate_form_employee(
    case_id: str,
    body: GenerateFormBody,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """Generate a pre-filled PDF from the caller's OWN vault profile for their case.

    Ownership-gated (require_case_access) and consent-gated. The profile is loaded
    scoped to (case_id, employee_id=caller.id) so a caller can only ever pre-fill
    from their own vault row.
    """
    require_case_access(case_id, user)
    employee_id = str(user.get("id") or "")
    if not _check_consent(case_id, employee_id):
        raise HTTPException(
            status_code=403,
            detail=(
                "No valid immigration consent on record for this case. "
                "Please complete the consent step first."
            ),
        )
    profile = _load_profile_for_case_employee(case_id, employee_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No immigration profile found for this case.",
        )
    return _generate_and_report(case_id, profile, body.form_id, employee_id, "employee")
