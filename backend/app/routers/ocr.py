"""[AIQ-1148] General document-OCR endpoint.

POST /api/ocr/process — accepts a document upload + optional document_type, runs it
through Mistral Document AI (the Render-native OCR engine) and returns the extracted
markdown + page count. The reusable OCR layer every document flow (expense receipts,
leases, visa docs) calls.

GDPR/PHI: the OCR'd text is document content — never log ``raw_markdown``. Structured
per-type field extraction (which must ``mask_pii`` before any LLM call) is a follow-up
(AIQ-1149+); ``extracted_fields`` is ``{}`` for now.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db
from ..services.mistral_ocr_client import mistral_ocr_document
from ..services.receipt_field_extractor import extract_expense_fields
from ..services.upload_validator import ALLOWED_MIME, read_and_validate

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

# Document types the endpoint accepts; 'generic' is the catch-all. Per-type structured
# field extraction is a deliberate follow-up — this layer returns OCR text for all types.
_ALLOWED_DOCUMENT_TYPES = frozenset(
    {"expense_receipt", "lease", "visa_document", "bank_statement", "payslip", "generic"}
)

_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB, matching the passport-OCR path


def _caller_company_id(user: Dict[str, Any]) -> Optional[str]:
    """Caller's OWN company (tenant) for the persisted row — mirrors ai_decisions._caller_company_id."""
    uid = user.get("id")
    profile = db.get_profile_record(uid) if uid else None
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id and uid:
        company_id = db.get_hr_company_id(uid)
    return str(company_id) if company_id else None


@router.post("/process")
async def process_document(
    file: UploadFile = File(..., description="Document to OCR — PDF, DOCX, XLSX, PNG or JPEG (max 10 MB)"),
    document_type: str = Form("generic"),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """OCR an uploaded document via Mistral Document AI → {raw_markdown, pages_count, extracted_fields}."""
    dt = (document_type or "generic").strip().lower()
    if dt not in _ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported_document_type:{dt}")

    if not (os.environ.get("MISTRAL_API_KEY") or "").strip():
        raise HTTPException(
            status_code=500,
            detail="OCR is not configured: MISTRAL_API_KEY is not set.",
        )

    content, safe_name, mime = await read_and_validate(
        file, allowed_mime=ALLOWED_MIME, max_bytes=_MAX_BYTES
    )

    try:
        result = mistral_ocr_document(content, mime)
    except Exception as exc:  # upstream/HTTP error from Mistral
        log.warning("ocr_process: Mistral OCR failed type=%s mime=%s err=%s", dt, mime, exc)
        raise HTTPException(status_code=502, detail="ocr_upstream_error")

    raw_markdown = result.get("markdown", "") or ""
    pages_count = int(result.get("pages_count", 0) or 0)
    # [AIQ-1149] Structured fields for expense receipts; other document_types keep {} (future work).
    extracted_fields: Dict[str, Any] = {}
    if dt == "expense_receipt":
        try:
            extracted_fields = await extract_expense_fields(raw_markdown)
        except Exception as exc:  # fail-soft — still return the OCR text
            log.warning("ocr_process: expense field extraction failed err=%s", exc)

    ocr_id = str(uuid.uuid4())
    # Defensive persist: document_ocr_results is applied out-of-band, so a missing table
    # must not fail the request — the OCR text is still returned. Never log raw_markdown.
    try:
        company_id = _caller_company_id(user)
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO document_ocr_results "
                    "(id, company_id, uploaded_by, document_type, source_filename, "
                    " mime_type, pages_count, raw_markdown, extracted_fields) "
                    "VALUES (:id, :cid, :uid, :dt, :fn, :mime, :pc, :md, CAST(:ef AS jsonb))"
                ),
                {
                    "id": ocr_id,
                    "cid": company_id,
                    "uid": user.get("id"),
                    "dt": dt,
                    "fn": safe_name,
                    "mime": mime,
                    "pc": pages_count,
                    "md": raw_markdown,
                    "ef": "{}",
                },
            )
    except Exception as exc:
        log.warning("ocr_process: document_ocr_results insert skipped id=%s err=%s", ocr_id, exc)

    return {
        "id": ocr_id,
        "document_type": dt,
        "raw_markdown": raw_markdown,
        "pages_count": pages_count,
        "extracted_fields": extracted_fields,
    }
