"""
Document pre-screening pipeline endpoints  (AIQ-13-B/C/E)

POST /api/hr/cases/{case_id}/prescreening
    Saves a pre-screening result and fires the HR reviewer notification.

GET  /api/hr/cases/{case_id}/prescreening
    Returns all pre-screening results for a case, newest first.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth_deps import require_admin_or_hr
from ..services.prescreening_notification import (
    send_prescreening_complete_email,
    get_reviewer_email_for_case,
)
from ...services.supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

router = APIRouter(tags=["prescreening"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class PrescreeningResultIn(BaseModel):
    upload_id: str
    document_type: str                     # e.g. "Passport", "Work Permit"
    employee_name: str
    type_match: bool = True
    expiry_valid: bool = True
    expiry_date: Optional[str] = None      # ISO date YYYY-MM-DD
    name_match: bool = True
    name_found: Optional[str] = None
    flags: List[str] = []
    confidence: float = 1.0
    ai_summary: Optional[str] = None


class PrescreeningResultOut(BaseModel):
    id: str
    upload_id: str
    document_type: str
    type_match: bool
    expiry_valid: bool
    expiry_date: Optional[str]
    name_match: bool
    name_found: Optional[str]
    flags: List[str]
    confidence: float
    ai_summary: Optional[str]
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/api/hr/cases/{case_id}/prescreening",
    status_code=201,
    summary="Save a prescreening result and notify the HR reviewer",
)
def submit_prescreening_result(
    case_id: str,
    body: PrescreeningResultIn,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """
    Called by the AI pipeline (AIQ-13-C) after document analysis completes.

    1. Writes the result to prescreening_results.
    2. Looks up the HR reviewer's email from relocation_cases.hr_user_id → users.email.
    3. Fires the prescreening completion email (fire-and-forget; never blocks response).
    """
    supabase = get_supabase_admin_client()

    result_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # 1. Persist the result
    payload: Dict[str, Any] = {
        "id": result_id,
        "upload_id": body.upload_id,
        "type_match": body.type_match,
        "expiry_valid": body.expiry_valid,
        "expiry_date": body.expiry_date,
        "name_match": body.name_match,
        "name_found": body.name_found,
        "flags": body.flags,
        "confidence": body.confidence,
        "ai_summary": body.ai_summary,
        "created_at": now,
    }

    insert_resp = supabase.table("prescreening_results").insert(payload).execute()
    if not insert_resp.data:
        log.error("prescreening_results insert failed for case %s", case_id)
        raise HTTPException(status_code=500, detail="Failed to save prescreening result.")

    # 2. Build a human-readable result summary
    flag_count = len(body.flags)
    if flag_count == 0:
        result_summary = body.ai_summary or "All checks passed."
    else:
        flag_list = "; ".join(body.flags)
        result_summary = body.ai_summary or f"{flag_count} flag{'s' if flag_count != 1 else ''}: {flag_list}"

    # 3. Resolve reviewer email and fire notification (best-effort)
    reviewer_email = get_reviewer_email_for_case(case_id)
    if reviewer_email:
        send_prescreening_complete_email(
            to=reviewer_email,
            employee_name=body.employee_name,
            document_type=body.document_type,
            case_id=case_id,
            result_summary=result_summary,
            flag_count=flag_count,
        )
    else:
        log.warning(
            "Could not resolve reviewer email for case %s — notification skipped",
            case_id,
        )

    return {
        "id": result_id,
        "case_id": case_id,
        "flag_count": flag_count,
        "notification_sent": reviewer_email is not None,
        "created_at": now,
    }


@router.get(
    "/api/hr/cases/{case_id}/prescreening",
    summary="List pre-screening results for a case",
)
def list_prescreening_results(
    case_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> List[Dict[str, Any]]:
    """
    Returns all prescreening results linked to uploads on this case,
    ordered newest-first.
    """
    supabase = get_supabase_admin_client()

    # Get all upload IDs for this case
    uploads_resp = (
        supabase.table("document_uploads")
        .select("id")
        .eq("case_id", case_id)
        .execute()
    )
    if not uploads_resp.data:
        return []

    upload_ids = [row["id"] for row in uploads_resp.data]

    results_resp = (
        supabase.table("prescreening_results")
        .select("*")
        .in_("upload_id", upload_ids)
        .order("created_at", desc=True)
        .execute()
    )
    return results_resp.data or []
