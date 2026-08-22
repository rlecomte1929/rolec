"""[W1-3] HR uploads a contract; the intake is proposed, reviewed, and only then stored.

    POST /api/hr/cases/{case_id}/intake-extraction/propose   (multipart: file)
    POST /api/hr/cases/{case_id}/intake-extraction/confirm   (json: fields)

Andrea's case is why this exists: her employer holds an Irish employment contract carrying
her name, role, salary, start date and work location, and the platform asks her to retype
all of it. `propose` reads the document; `confirm` stores what a human approved.

THE GATE IS THE POINT. `propose` NEVER writes — it runs OCR + extraction and returns a
proposal. `confirm` is the only writer, and it stores the fields in ITS OWN body, not a
server-side cache of the proposal. That is deliberate: it makes "HR edited the value before
confirming" the normal path rather than a special case, and it makes it impossible for a
proposal to reach the draft without a human having sent it back. There is no confidence
score at which anything auto-accepts.

REUSES, does not duplicate: `mistral_ocr_document` (the AIQ-1148 OCR layer), `read_and_validate`
(upload limits/mime), `intake_contract_extractor` (LLM + mask_pii), and
`case_assignments.intake_draft` (the wizard's own store).

Written in the FLAT snake_case wizard shape, from RECOGNISED_INTAKE_KEYS — not the nested
CaseDraftDTO the task text suggested. `intake_draft_to_case_draft` cannot read the nested
shape, and storing it is the recorded T18 failure: accepted, echoed back by GET, and then
reported as entirely missing by the submit guard.

Tenant scoping mirrors hr_case_detail: 404 (not 403) on mismatch so case ids can't be
enumerated by status code.

Dual-registered in backend/main.py AND backend/app/main.py (CLAUDE.md 405 rule).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.intake_contract_extractor import (
    PROPOSED_FIELDS,
    empty_extraction,
    extract_intake_fields,
    proposal_to_draft_patch,
)
from ..services.mistral_ocr_client import mistral_ocr_document
from ..services.upload_validator import ALLOWED_MIME, read_and_validate

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hr/cases", tags=["hr-intake-extraction"])

_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB, matching /api/ocr/process
_ALLOWED_DOCUMENT_TYPES = frozenset({"employment_contract", "offer_letter"})

# Stamped on every field this flow writes, so a later reader can tell an HR-extracted
# value from one the employee typed. Never overwritten by a re-run.
PROVENANCE = "hr_extracted"


class ProposedField(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0


class ProposeResponse(BaseModel):
    case_id: str
    assignment_id: str
    document_type: str
    pages_count: int
    fields: Dict[str, ProposedField]
    # Always false. Present so the contract states the guarantee rather than implying it.
    written: bool = False


class ConfirmBody(BaseModel):
    # {field: value} or {field: {"value": ...}} — HR's EDITED values, not the proposal.
    fields: Dict[str, Any]


class ConfirmResponse(BaseModel):
    case_id: str
    assignment_id: str
    written_fields: List[str]
    skipped_fields: List[str]
    provenance: str = PROVENANCE
    intake_draft: Dict[str, Any]


def _require_case_access(case_id: str, org_id: str) -> Dict[str, Any]:
    """404 (not 403) on tenant mismatch — mirrors hr_case_detail._require_case_access."""
    row = db.get_relocation_case(case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_company_id = row.get("company_id")
    if case_company_id and case_company_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


def _assignment_id_for_case(case_id: str) -> str:
    assignment = db.get_assignment_by_case_id(case_id)
    if not assignment or not assignment.get("id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This case has no assignment to prefill.",
        )
    return str(assignment["id"])


@router.post("/{case_id}/intake-extraction/propose", response_model=ProposeResponse)
async def propose_intake_from_document(
    case_id: str,
    file: UploadFile = File(..., description="Employment contract or offer letter (max 10 MB)"),
    document_type: str = Form("employment_contract"),
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ProposeResponse:
    """OCR + extract. Returns a proposal and writes NOTHING."""
    dtype = (document_type or "employment_contract").strip().lower()
    if dtype not in _ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported_document_type:{dtype}")

    _require_case_access(case_id, org_id)
    assignment_id = _assignment_id_for_case(case_id)

    if not (os.environ.get("MISTRAL_API_KEY") or "").strip():
        raise HTTPException(status_code=500, detail="OCR is not configured: MISTRAL_API_KEY is not set.")

    content, _safe_name, mime = await read_and_validate(
        file, allowed_mime=ALLOWED_MIME, max_bytes=_MAX_BYTES
    )
    try:
        ocr = mistral_ocr_document(content, mime)
    except Exception as exc:
        log.warning("intake_extraction: OCR failed case_id=%s mime=%s err=%s", case_id, mime, exc)
        raise HTTPException(status_code=502, detail="ocr_upstream_error")

    raw_markdown = ocr.get("markdown", "") or ""
    # Never log raw_markdown or the extraction — both are document content (CLAUDE.md).
    fields = await extract_intake_fields(raw_markdown)

    return ProposeResponse(
        case_id=case_id,
        assignment_id=assignment_id,
        document_type=dtype,
        pages_count=int(ocr.get("pages_count", 0) or 0),
        fields={k: ProposedField(**v) for k, v in fields.items()},
        written=False,
    )


@router.post("/{case_id}/intake-extraction/confirm", response_model=ConfirmResponse)
def confirm_intake_prefill(
    case_id: str,
    body: ConfirmBody,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ConfirmResponse:
    """Store the fields HR approved. The ONLY writer in this flow."""
    _require_case_access(case_id, org_id)
    assignment_id = _assignment_id_for_case(case_id)

    patch = proposal_to_draft_patch(body.fields or {})
    skipped = [f for f in PROPOSED_FIELDS if f not in patch]
    if not patch:
        raise HTTPException(
            status_code=400,
            detail="No usable fields to write — every value was empty or failed validation.",
        )

    patch[f"{PROVENANCE}_fields"] = sorted(patch.keys())
    result = db.merge_assignment_intake_draft_as_hr(assignment_id, patch)
    if result is None:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    log.info(
        "intake_extraction confirm case_id=%s assignment_id=%s fields=%s",
        case_id, assignment_id, sorted(k for k in patch if k != f"{PROVENANCE}_fields"),
    )
    return ConfirmResponse(
        case_id=case_id,
        assignment_id=assignment_id,
        written_fields=sorted(k for k in patch if k != f"{PROVENANCE}_fields"),
        skipped_fields=skipped,
        intake_draft=result.get("intake_draft", {}),
    )
