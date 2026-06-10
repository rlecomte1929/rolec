"""BL-OCR.2 / AIQ-748 — immigration document upload + list endpoints.

POST /api/immigration/cases/{case_id}/documents
  Auth: any authenticated user assigned to the case (employee or HR via
  case_assignments), or admin. Accepts multipart 'file'. PDF/PNG/JPEG/WEBP/TIFF
  only, ≤ 20 MiB (matches the immigration-documents bucket cap). Validates
  size+MIME (upload_validator, libmagic), uploads to the private bucket, inserts
  an immigration_documents row, and returns {document_id, storage_path,
  ocr_status:'pending'}.

GET /api/immigration/cases/{case_id}/documents
  Same access scoping; returns the case's documents (newest first) with their
  OCR status + result for the employee/HR document viewer (BL-OCR.4 / AIQ-750).

WIRED (CLAUDE.md hard gate): registered in BOTH backend/main.py and
backend/app/main.py.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db
from ..services.document_extraction_queue import run_extraction
from ..services.document_upload_service import store_immigration_document

router = APIRouter(prefix="/api/immigration", tags=["immigration-documents"])
log = logging.getLogger(__name__)

# Mirrors the immigration_documents.mime_type CHECK + bucket allowlist (BL-OCR.1).
ALLOWED_MIME = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/tiff"}
)
MAX_BYTES = 20 * 1024 * 1024  # 20 MiB — the bucket's file_size_limit.


def _resolve_accessible_case(case_id: str, user: Dict[str, Any]) -> str:
    """Return the case_assignments.case_id the caller may access, else 404.

    Mirrors the immigration_documents RLS: the caller must be the assigned
    employee or HR (case_assignments.employee_user_id / hr_user_id), or admin.
    Accepts either the assignment PK or the case_id FK as the path param, and
    returns the canonical case_id (the column stored on immigration_documents).
    A single not-found/forbidden code (404) avoids leaking case existence.
    """
    uid = str(user.get("id") or "")
    is_admin = 1 if user.get("is_admin") else 0
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT ca.case_id FROM public.case_assignments ca "
                "WHERE (ca.id = :cid OR ca.case_id = :cid) "
                "  AND (:is_admin = 1 OR ca.employee_user_id = :uid "
                "       OR ca.hr_user_id = :uid) "
                "LIMIT 1"
            ),
            {"cid": str(case_id), "uid": uid, "is_admin": is_admin},
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found or not accessible")
    return row[0]


@router.post("/cases/{case_id}/documents")
async def upload_immigration_document(
    case_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Validate + store an uploaded immigration document. 413 if oversized,
    415 if an unsupported type, 404 if the case isn't accessible."""
    resolved_case_id = _resolve_accessible_case(case_id, user)

    # Lazy import: upload_validator hard-imports libmagic, a Render base-image dep
    # not present in every env — keep it out of module import (policy-upload pattern).
    from ..services.upload_validator import read_and_validate

    # Size + MIME gate (raises 413 file_too_large / 415 unsupported_type).
    content, safe_name, mime = await read_and_validate(
        file, allowed_mime=ALLOWED_MIME, max_bytes=MAX_BYTES
    )

    try:
        record = store_immigration_document(
            case_id=resolved_case_id,
            uploaded_by=str(user.get("id") or ""),
            file_name=safe_name,
            content=content,
            mime_type=mime,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — storage/DB failure → 502
        log.error(
            "immigration_document upload failed case_id=%s: %s",
            resolved_case_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=502, detail="Document storage failed. Please retry."
        )

    # BL-OCR.3: kick off classification + extraction in the background so the
    # upload returns immediately with ocr_status='pending'; the job advances it
    # to 'done'/'failed'. Fail-soft inside run_extraction.
    background_tasks.add_task(
        run_extraction,
        document_id=record["document_id"],
        storage_path=record["storage_path"],
        mime_type=mime,
        file_name=safe_name,
    )
    return record


@router.get("/cases/{case_id}/documents")
def list_immigration_documents(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List a case's uploaded documents (newest first) for the document viewer.

    Access is scoped identically to the upload endpoint — assigned employee/HR
    or admin — so 404 is returned for any case the caller can't see, never a
    leak of another tenant's documents.
    """
    resolved_case_id = _resolve_accessible_case(case_id, user)

    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, file_name, mime_type, file_size_bytes, ocr_status, "
                "       ocr_result, uploaded_by, created_at "
                "FROM public.immigration_documents "
                "WHERE case_id = :cid "
                "ORDER BY created_at DESC"
            ),
            {"cid": resolved_case_id},
        ).mappings().all()

    documents = [
        {
            "document_id": r["id"],
            "file_name": r["file_name"],
            "mime_type": r["mime_type"],
            "file_size_bytes": r["file_size_bytes"],
            "ocr_status": r["ocr_status"],
            "ocr_result": r["ocr_result"],
            "uploaded_by": r["uploaded_by"],
            "uploaded_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"case_id": resolved_case_id, "documents": documents}
