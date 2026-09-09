"""
data_sheet.py — the Document Data Sheet read endpoint (Phase 1).

    GET /api/cases/{case_id}/datasheet?audience=employee|hr&lang=en|local&mode=full|sparse

One composed, corridor-agnostic view of a case's data sheet: steps → fields → value +
provenance, with the consult-professional firewall preserved. Deterministic; the serve path
imports no LLM (see backend/app/services/data_sheet_service.py, a SERVING_ROOT).

Read-only. Field edits + write-back to the canonical store are Phase 2.

Registered in BOTH backend/app/main.py and backend/main.py (the 405 dual-registration rule) —
prod boots backend.main:app, so a router wired only into the modular app 405s in production.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from .. import schemas
from ..auth_deps import get_current_user
from ..services.case_service import _assert_case_access
from ..services.data_sheet_service import build_data_sheet
from ..services.data_sheet_write_service import apply_field_edit
from ..services.datasheet_export import build_datasheet_pdf

router = APIRouter(prefix="/api/cases", tags=["cases"])
logger = logging.getLogger(__name__)


class DataSheetFieldEdit(BaseModel):
    value: Optional[str] = None


@router.get("/{case_id}/datasheet", response_model=schemas.DataSheetDTO)
def get_case_datasheet(
    case_id: str,
    audience: str = "employee",
    lang: str = "en",
    mode: str = "full",
    user: Dict[str, Any] = Depends(get_current_user),
) -> schemas.DataSheetDTO:
    # Resolve access AND the canonical id to key SQL on (the {case_id} path param may be an
    # assignment id). Key the read-model on the RETURN VALUE, never the raw param (AIQ-1775).
    resolved_case_id = _assert_case_access(user, case_id)
    return build_data_sheet(resolved_case_id, audience=audience, lang=lang, mode=mode)


@router.patch("/{case_id}/datasheet/fields/{field_id}", response_model=schemas.DataSheetDTO)
def edit_case_datasheet_field(
    case_id: str,
    field_id: str,
    payload: DataSheetFieldEdit,
    audience: str = "employee",
    lang: str = "en",
    mode: str = "full",
    user: Dict[str, Any] = Depends(get_current_user),
) -> schemas.DataSheetDTO:
    # Persist a user's edit (form-local write-back) and return the recomposed sheet.
    # Consult-professional fields are rejected inside apply_field_edit (422).
    resolved_case_id = _assert_case_access(user, case_id)
    return apply_field_edit(
        resolved_case_id, field_id, payload.value, user,
        audience=audience, lang=lang, mode=mode,
    )


@router.get("/{case_id}/datasheet/pdf")
def get_case_datasheet_pdf(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    # Export the case's data sheet as a print-grade PDF (render_data_sheet, channel-aware).
    # The employee's takeaway artifact for corridors with no fillable government form.
    resolved_case_id = _assert_case_access(user, case_id)
    pdf_bytes, filename = build_datasheet_pdf(resolved_case_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="No data sheet available for this case")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
