"""BL-OCR.2 / AIQ-748 — immigration document upload (Supabase Storage + DB).

Uploads an already-validated file to the private ``immigration-documents`` bucket
and records it in ``public.immigration_documents`` with ``ocr_status='pending'``
for the OCR worker to pick up. Storage path: ``<case_id>/<uuid>.<ext>``.

The size + MIME gate runs upstream in the router via ``upload_validator``
(libmagic magic-byte detection + a 20 MiB ceiling, matching the bucket). A real
AV scan (ClamAV / Supabase scan) is a follow-up — the Render-native runtime
can't apt-install clamav. TODO [BL-OCR-followup]: wire an AV pass before insert.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import text

from ...database import db
from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

BUCKET_IMMIGRATION_DOCS = "immigration-documents"

# Extension per MIME — must stay within the immigration_documents.mime_type CHECK
# + the bucket allowlist (BL-OCR.1 migration).
_EXT_BY_MIME: Dict[str, str] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/tiff": "tiff",
}


def store_immigration_document(
    *,
    case_id: str,
    uploaded_by: str,
    file_name: str,
    content: bytes,
    mime_type: str,
) -> Dict[str, Any]:
    """Upload ``content`` to the immigration-documents bucket and insert a row.

    Returns ``{document_id, storage_path, ocr_status}``. Raises on storage or DB
    failure (the router maps that to a 502).
    """
    doc_id = str(uuid.uuid4())
    ext = _EXT_BY_MIME.get(mime_type, "bin")
    storage_path = f"{case_id}/{doc_id}.{ext}"

    client = get_supabase_admin_client()
    # upsert=false: a fresh uuid path never collides, and we never clobber.
    client.storage.from_(BUCKET_IMMIGRATION_DOCS).upload(
        storage_path,
        content,
        {"content-type": mime_type, "upsert": "false"},
    )

    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO immigration_documents "
                "(id, case_id, uploaded_by, file_name, storage_path, mime_type, "
                "file_size_bytes, ocr_status, created_at, updated_at) "
                "VALUES (:id, :case_id, :uploaded_by, :file_name, :storage_path, "
                ":mime_type, :size, 'pending', :now, :now)"
            ),
            {
                "id": doc_id,
                "case_id": case_id,
                "uploaded_by": uploaded_by,
                "file_name": file_name,
                "storage_path": storage_path,
                "mime_type": mime_type,
                "size": len(content),
                "now": now,
            },
        )

    log.info(
        "immigration_document stored document_id=%s case_id=%s size=%d mime=%s",
        doc_id, case_id, len(content), mime_type,
    )
    return {"document_id": doc_id, "storage_path": storage_path, "ocr_status": "pending"}
