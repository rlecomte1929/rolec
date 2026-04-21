"""
Typed error hierarchy for the policy intake pipeline.

Each error carries a stable `code` slug (used by API boundary layers to
surface a deterministic error identifier to the client) and an optional
structured `detail` dict (filename, sizes, sniff diagnostics, …) that
never contains secrets, absolute filesystem paths, or credentials.

HTTP status code mapping lives in the API layer (see backend/main.py
upload endpoint) — the exception itself is transport-agnostic.

Audit reference: Prompt 0 GAPs 003, 004, 009, 010; Prompt A §9 R1–R4.
"""
from __future__ import annotations

from typing import Optional


class PolicyIntakeError(Exception):
    """Base class for typed policy-intake rejection errors."""

    code: str = "INTAKE_ERROR"

    def __init__(self, message: str, *, detail: Optional[dict] = None) -> None:
        super().__init__(message)
        self.detail: dict = detail or {}


class UnsupportedFileTypeError(PolicyIntakeError):
    """R1 — Magic-byte sniffing could not identify the file as PDF or DOCX."""

    code = "UNSUPPORTED_FILE_TYPE"


class MalformedDocumentError(PolicyIntakeError):
    """
    R2 — Sniffing identified the format but the parser failed on truncated
    or internally-corrupt bytes.
    """

    code = "MALFORMED_DOCUMENT"


class EncryptedDocumentError(PolicyIntakeError):
    """
    R3 — Document is password-protected (PDF) or encrypted OLE2 (Office).
    We refuse to prompt for a password; HR must upload a decrypted copy.
    """

    code = "ENCRYPTED_DOCUMENT"


class DocumentSizeError(PolicyIntakeError):
    """R4 — File is empty, too small to be a real document, or exceeds the ceiling."""

    code = "DOCUMENT_SIZE_INVALID"


class IntakePipelineUnavailableError(PolicyIntakeError):
    """
    Raised when a dependency the intake pipeline relies on (pdfplumber,
    python-docx, etc.) is missing at runtime. Fail-closed: we do NOT
    treat a missing parser as "not encrypted" / "valid content"; we
    surface a 503 so the caller knows the upload can't be validated right
    now. Maps to HTTP 503 (Service Unavailable) at the API boundary.
    """

    code = "INTAKE_PIPELINE_UNAVAILABLE"
