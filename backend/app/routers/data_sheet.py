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
from typing import Any, Dict

from fastapi import APIRouter, Depends

from .. import schemas
from ..auth_deps import get_current_user
from ..services.case_service import _assert_case_access
from ..services.data_sheet_service import build_data_sheet

router = APIRouter(prefix="/api/cases", tags=["cases"])
logger = logging.getLogger(__name__)


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
