"""BL-OCR.3 / AIQ-948 — wire uploaded documents to the C1-05 extraction runtime.

After BL-OCR.2 stores a document (ocr_status='pending'), the upload endpoint
schedules ``run_extraction`` as a FastAPI background task so the OCR/LLM work
never blocks the upload response. The job:

  1. Downloads the file bytes from the private 'immigration-documents' bucket.
  2. Classifies the document type (PASSPORT | CONTRACT | PAYSLIP | OTHER). The
     C1-05 classifier (C1-04a) is not yet on main, so we use the lightweight
     filename/MIME heuristic the BL-OCR.3 brief sanctions for the MVP.
  3. For PASSPORT, runs the existing C1-05 ``extract_passport`` agent (GPT-4o
     vision) and records structured fields + confidence. Other types record the
     classification only (their extractors are separate C1-05 tasks).
  4. UPDATE immigration_documents SET ocr_status='done', ocr_result=<json>.

Fail-soft by contract: any download/classify/extract/DB error sets
ocr_status='failed' and never raises into the request (it runs detached).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text

from ...database import db
from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

BUCKET_IMMIGRATION_DOCS = "immigration-documents"

# Fields lifted off the C1-05 PassportExtractionResult into ocr_result.fields.
# getattr-based (not dataclasses.asdict) so the extractor stays a lazy import.
_PASSPORT_FIELDS = (
    "surname", "given_names", "date_of_birth", "gender", "place_of_birth",
    "nationality", "issuing_country", "passport_number", "issue_date",
    "expiry_date", "mrz_line1", "mrz_line2", "low_quality", "low_quality_reason",
)


def classify_document(file_name: Optional[str], mime_type: Optional[str]) -> str:
    """MVP heuristic classifier (the C1-05 classifier isn't on main yet).

    Returns PASSPORT | CONTRACT | PAYSLIP | OTHER from filename keywords.
    """
    name = (file_name or "").lower()
    if "passport" in name:
        return "PASSPORT"
    if "contract" in name:
        return "CONTRACT"
    if "payslip" in name or "pay_slip" in name or "salary" in name:
        return "PAYSLIP"
    return "OTHER"


def _update_status(
    document_id: str, status: str, ocr_result: Optional[Dict[str, Any]] = None
) -> None:
    now = datetime.utcnow().isoformat()
    params: Dict[str, Any] = {"id": document_id, "status": status, "now": now}
    set_clause = "ocr_status = :status, updated_at = :now"
    if ocr_result is not None:
        # JSONB column: a json string assigns via Postgres's text→jsonb assignment
        # cast (same idiom as update_policy_document.extracted_metadata).
        set_clause += ", ocr_result = :ocr_result"
        params["ocr_result"] = json.dumps(ocr_result)
    with db.engine.begin() as conn:
        conn.execute(
            text(f"UPDATE immigration_documents SET {set_clause} WHERE id = :id"),
            params,
        )


def _passport_ocr_result(result: Any) -> Dict[str, Any]:
    fields = {f: getattr(result, f, None) for f in _PASSPORT_FIELDS}
    per_field = getattr(result, "confidence", None) or {}
    # Overall confidence = the weakest field we read (conservative for review UIs).
    overall = round(min(per_field.values()), 2) if per_field else None
    return {
        "document_type": "PASSPORT",
        "fields": fields,
        "confidence": overall,
        "per_field_confidence": per_field,
    }


async def run_extraction(
    *,
    document_id: str,
    storage_path: str,
    mime_type: str,
    file_name: Optional[str] = None,
) -> None:
    """Background OCR/extraction for one uploaded document. Fail-soft."""
    try:
        _update_status(document_id, "processing")

        client = get_supabase_admin_client()
        content = client.storage.from_(BUCKET_IMMIGRATION_DOCS).download(storage_path)

        doc_type = classify_document(file_name, mime_type)
        if doc_type == "PASSPORT":
            # Lazy import: ocr_passport_extractor pulls the OpenAI SDK (GPT-4o).
            from .ocr_passport_extractor import extract_passport

            result = await extract_passport(content, mime_type)
            ocr_result = _passport_ocr_result(result)
        else:
            # CONTRACT/PAYSLIP extractors are separate C1-05 tasks; record the
            # classification so the doc isn't stuck 'pending'.
            ocr_result = {"document_type": doc_type, "fields": {}, "confidence": None}

        _update_status(document_id, "done", ocr_result)
        log.info(
            "ocr_extraction done document_id=%s type=%s", document_id, doc_type
        )
    except Exception as exc:  # noqa: BLE001 — runs detached; never raise
        log.warning(
            "ocr_extraction failed document_id=%s: %s", document_id, exc, exc_info=True
        )
        try:
            _update_status(document_id, "failed")
        except Exception:  # noqa: BLE001
            log.error("ocr_extraction could not mark failed document_id=%s", document_id)
