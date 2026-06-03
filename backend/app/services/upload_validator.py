"""
SEC-006 — server-side upload validation.

Single entry point ``read_and_validate`` that every binary-file upload endpoint
routes through. It enforces, in order:

  1. size ceiling (20 MiB)           → HTTP 413
  2. content-based MIME allowlist     → HTTP 415   (python-magic, never the
     client-supplied ``Content-Type`` or file extension)
  3. filename sanitisation           → HTTP 400 when nothing survives

The detected MIME (not the claimed one) is returned so callers can persist an
honest ``content-type`` on the storage object.

System dependency: ``python-magic`` needs the ``libmagic`` C library. Render's
``python:3.11-slim`` image ships it via apt; see ``backend/README.md``.

Audit reference: AIQ-478 / SEC-006.
"""
from __future__ import annotations

from typing import Final, Tuple
from uuid import uuid4

import magic
from fastapi import HTTPException, UploadFile
from werkzeug.utils import secure_filename

# Base allowlist from the SEC-006 spec: PDF, DOCX, XLSX, PNG, JPEG.
ALLOWED_MIME: Final[frozenset] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/png",
        "image/jpeg",
    }
)

# Image-only subset for photo/scan endpoints (passport OCR). WebP is included
# because the existing immigration upload flow already accepts it and the live
# `case-documents` bucket allows it.
ALLOWED_IMAGE_MIME: Final[frozenset] = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
    }
)

MAX_BYTES: Final[int] = 20 * 1024 * 1024  # 20 MiB


def detect_mime(content: bytes) -> str:
    """Content-based MIME sniff via libmagic. Never trusts the caller."""
    return magic.from_buffer(content, mime=True)


def sanitize_filename(filename: str | None) -> str:
    """
    werkzeug.secure_filename, with a deterministic fallback so a name that
    sanitises to empty (e.g. ``../../``) never yields an unnamed object.
    Path traversal is stripped by secure_filename; the caller still builds the
    final storage path from a server-generated uuid, so the name is cosmetic.
    """
    return secure_filename(filename or "") or f"upload-{uuid4().hex}.bin"


async def read_and_validate(
    file: UploadFile,
    *,
    allowed_mime: frozenset = ALLOWED_MIME,
    max_bytes: int = MAX_BYTES,
) -> Tuple[bytes, str, str]:
    """
    Read an UploadFile fully and validate it.

    Returns ``(content, sanitized_name, detected_mime)``.

    Raises ``HTTPException``:
      * 413 ``file_too_large``      — body exceeds ``max_bytes``
      * 415 ``unsupported_type:..`` — detected MIME not in ``allowed_mime``
      * 400 ``empty_file`` / ``invalid_filename`` — empty body / no usable name
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="file_too_large")

    mime = detect_mime(content)
    if mime not in allowed_mime:
        raise HTTPException(status_code=415, detail=f"unsupported_type:{mime}")

    safe = sanitize_filename(file.filename)
    if not safe:
        raise HTTPException(status_code=400, detail="invalid_filename")

    return content, safe, mime


def build_storage_path(tenant_scope_id: str, safe_name: str) -> str:
    """
    Server-generated object key: ``{tenant}/{uuid4}/{safe_name}``.

    The uuid4 segment guarantees uniqueness and makes the path
    unguessable; ``safe_name`` is already sanitised. The client never
    influences the path layout, so traversal is structurally impossible.
    """
    scope = secure_filename(tenant_scope_id or "") or "unscoped"
    return f"{scope}/{uuid4()}/{safe_name}"
