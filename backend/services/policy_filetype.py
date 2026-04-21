"""
Magic-byte file-type sniff + size + encryption gate for policy uploads.

The legacy upload path trusted the filename extension. That's unsafe:
a caller can rename a zip of executables to `policy.docx` and the parser
will trip later, deep in the stack. This module runs the checks in the
order that matters — size first (cheap), then magic-byte sniff (cheap),
then encryption check (requires one pdfplumber open on PDFs only).

Audit reference: Prompt 0 GAPs 009, 010, 003, 004.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Final, Literal

from .policy_intake_errors import (
    DocumentSizeError,
    EncryptedDocumentError,
    UnsupportedFileTypeError,
)

log = logging.getLogger(__name__)

# Default ceiling: 20 MB. Override via env for large-corpus testing.
DEFAULT_MAX_UPLOAD_BYTES: Final[int] = 20 * 1024 * 1024
MAX_UPLOAD_BYTES_ENV: Final[str] = "RELOPASS_POLICY_UPLOAD_MAX_BYTES"

# PDF always begins with %PDF- in the first 8 bytes.
_PDF_MAGIC: Final[bytes] = b"%PDF-"
# DOCX is a zip container; zip signature is "PK\x03\x04" (local file header).
_ZIP_MAGIC: Final[bytes] = b"PK\x03\x04"

FileKind = Literal["pdf", "docx"]


def _max_upload_bytes() -> int:
    raw = os.getenv(MAX_UPLOAD_BYTES_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        v = int(raw)
        return v if v > 0 else DEFAULT_MAX_UPLOAD_BYTES
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES


def check_size(data: bytes) -> None:
    """
    Raises DocumentSizeError if `data` is empty or exceeds the ceiling.
    Both are mapped to HTTP 413 at the API boundary.
    """
    if not data:
        raise DocumentSizeError("Uploaded file is empty.")
    ceiling = _max_upload_bytes()
    if len(data) > ceiling:
        raise DocumentSizeError(
            f"Uploaded file is {len(data)} bytes; maximum is {ceiling} bytes."
        )


def sniff_file_kind(data: bytes) -> FileKind:
    """
    Identify file format from leading bytes. Returns 'pdf' or 'docx'.
    Raises UnsupportedFileTypeError if neither signature matches.
    The claimed filename / MIME type is intentionally ignored.
    """
    head = data[:8]
    if head.startswith(_PDF_MAGIC):
        return "pdf"
    if head.startswith(_ZIP_MAGIC):
        # DOCX is always a zip. We don't open the zip here — if it turns
        # out to be a generic zip the downstream parser will raise
        # MalformedDocumentError.
        return "docx"
    # Hex-encode the head for logs; never raise it back to the user
    # (could be attacker-controlled bytes).
    head_hex = head.hex() if head else "(empty)"
    log.info("sniff_file_kind: unrecognized magic bytes head=%s", head_hex)
    raise UnsupportedFileTypeError(
        "Unsupported file format. Only PDF and DOCX are accepted."
    )


def check_pdf_not_encrypted(data: bytes) -> None:
    """
    Raises EncryptedDocumentError if the PDF is password-protected.
    No-op for non-PDFs (caller is expected to have identified the kind first).
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError:  # pragma: no cover — pdfplumber is in requirements.txt
        return
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            # Probe the first page's metadata — encrypted PDFs raise here
            # (pdfminer raises PDFPasswordIncorrect / PDFEncryptionError).
            # Accessing pdf.metadata is fine on both paths.
            _ = pdf.metadata
            if pdf.pages:
                pdf.pages[0].extract_text()
    except Exception as ex:
        msg = (str(ex) or type(ex).__name__).lower()
        if "password" in msg or "encrypted" in msg:
            raise EncryptedDocumentError(
                "PDF is password-protected. Upload a decrypted copy."
            ) from ex
        # Other parse errors are surfaced as MalformedDocumentError by the
        # caller (we don't want to raise that here — keep the sniff-stage
        # concerns separate). Log and return normally.
        log.info("check_pdf_not_encrypted: non-encryption error surfaced: %s", ex)


def validate_upload_bytes(data: bytes) -> FileKind:
    """
    One-call gate for upload endpoints. Runs:
      1. size check
      2. magic-byte sniff
      3. PDF encryption check (skipped for DOCX)

    Returns the sniffed FileKind. Raises a PolicyIntakeError subclass on
    any rejection — the API layer maps the exception's http_status.
    """
    check_size(data)
    kind = sniff_file_kind(data)
    if kind == "pdf":
        check_pdf_not_encrypted(data)
    return kind
