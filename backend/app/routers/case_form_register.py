"""
[AIQ-1758] Register a reviewed prefilled data-sheet as a durable case artifact.

Endpoint (registered in BOTH backend/app/main.py AND backend/main.py):
  POST /api/cases/{case_id}/forms/{form_id}/register

Thin wrapper over prefilled_document_service.register_prefilled_document, which
inserts the case_form_documents row, writes the prefill audit, and advances the
form status. Reuses the ad-hoc router's auth/access shape.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..auth_deps import get_current_user
from ..services.case_service import _assert_case_access
from ..services.prefilled_document_service import register_prefilled_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["case-form-register"])


@router.post("/{case_id}/forms/{form_id}/register")
def register_prefilled_form(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Register the reviewed prefilled data-sheet for this CaseForm."""
    _assert_case_access(user, case_id)
    actor_id = user.get("auth_uuid") or user.get("id")
    try:
        return register_prefilled_document(case_id, form_id, actor_id=actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception("register: failed case_id=%s form_id=%s", case_id, form_id)
        raise HTTPException(status_code=500, detail="Failed to register prefilled document")
