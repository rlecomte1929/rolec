"""
Typed error hierarchy for the policy intake pipeline.

Before this module, the upload endpoint returned a generic 500 on any
extraction failure, with no distinction between "encrypted PDF",
"corrupt bytes", "wrong MIME", and "file too large". Clients couldn't
tell the user what went wrong, and logs masked what class of fixture
problem the upload surfaced.

Each error carries:
  - `error_code`: stable machine-readable slug that matches the
    upload_response UPLOAD_* constants.
  - `http_status`: the status the API layer SHOULD return (415, 413, 422).
  - A user-visible message (the `str()` form). Messages never contain
    secrets, absolute filesystem paths, or db connection strings.

Audit reference: Prompt 0 GAPs 003, 004, 009, 010; Prompt A §9 R1–R4.
"""
from __future__ import annotations


class PolicyIntakeError(Exception):
    """Base class for typed intake errors. Default status = 422."""

    error_code: str = "policy_intake_error"
    http_status: int = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UnsupportedFileTypeError(PolicyIntakeError):
    """Magic-byte sniffing could not identify the file as PDF or DOCX."""

    error_code = "unsupported_file_type"
    http_status = 415  # Unsupported Media Type


class MalformedDocumentError(PolicyIntakeError):
    """
    Sniffing identified the format but the parser could not produce text.
    Typically raised when pdfplumber or python-docx throws on truncated
    or internally-corrupt content.
    """

    error_code = "malformed_document"
    http_status = 422  # Unprocessable Entity


class EncryptedDocumentError(PolicyIntakeError):
    """
    PDF is password-protected (or otherwise encrypted). We refuse to
    prompt for the password; HR must upload a decrypted version.
    """

    error_code = "encrypted_document"
    http_status = 422


class DocumentSizeError(PolicyIntakeError):
    """File exceeds the configured upload size ceiling, or is empty."""

    error_code = "document_too_large"
    http_status = 413  # Payload Too Large
