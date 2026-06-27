"""
Admin policy analysis endpoint — AIQ-1219 PR2.

Accepts a PDF/DOCX file upload and returns a structured workflow summary
(tiers, tasks, timeline, cost range) derived from Fable 5 extraction.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..routers.admin import require_admin
from ..services.policy_extractor import extract_policy_with_diff
from ..services.policy_workflow_builder import build_workflow_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/policy-analysis", tags=["policy-analysis"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("")
def analyze_policy_document(
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    """Upload a PDF/DOCX and get a full workflow summary.

    Returns the extraction diff (regex + LLM merged) plus a derived
    workflow summary with tiers, tasks, timeline, and cost range.
    """
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {content_type}. Use PDF or DOCX.",
        )

    # Read with bounded size to prevent memory exhaustion from oversized uploads.
    chunks = []
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)  # 1 MB chunks
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(status_code=422, detail="File too large (50 MB max).")
        chunks.append(chunk)
    file_bytes = b"".join(chunks)
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Empty file.")

    file_type = ALLOWED_CONTENT_TYPES[content_type]
    t0 = time.monotonic()

    try:
        diff = extract_policy_with_diff(
            file_bytes, file_type, company_id=None,
        )
    except Exception:
        logger.exception("policy_analysis: extraction failed")
        raise HTTPException(status_code=500, detail="Extraction failed.")

    merged = diff.get("merged") or diff.get("regex_extracted") or {}
    summary = build_workflow_summary(merged)

    elapsed_ms = round((time.monotonic() - t0) * 1000)

    return {
        "workflow_summary": summary,
        "extraction": {
            "llm_used": diff.get("llm_used", False),
            "llm_unavailable_reason": diff.get("llm_unavailable_reason"),
            "model": (diff.get("llm_extracted") or {}).get("model"),
            "truncated": (diff.get("llm_extracted") or {}).get("truncated", False),
            "benefits_count": len(merged.get("benefits", [])),
        },
        "elapsed_ms": elapsed_ms,
    }
