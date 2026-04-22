"""
Magic-byte file-type sniff + size + encryption gate for policy uploads.

Upstream callers never see the raw filename — we sniff the leading bytes
and refuse anything that isn't clearly a PDF (`%PDF-`) or a DOCX
(ZIP-wrapped with a `word/document.xml` marker in the first 8 KiB). An
OLE2 compound-file header for a `.docx`-named upload signals an
encrypted Office package and is routed to EncryptedDocumentError.

Audit reference: Prompt 0 GAPs 003, 004, 009, 010.
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Final, Literal, Optional

from .policy_intake_errors import (
    DocumentSizeError,
    EncryptedDocumentError,
    IntakePipelineUnavailableError,
    UnsupportedFileTypeError,
)

log = logging.getLogger(__name__)

# --- Size bounds -------------------------------------------------------------

# 20 MiB default. Tune via env without code change.
DEFAULT_MAX_UPLOAD_BYTES: Final[int] = 20 * 1024 * 1024
MAX_UPLOAD_BYTES_ENV: Final[str] = "RELOPASS_POLICY_UPLOAD_MAX_BYTES"
# Any payload smaller than this cannot realistically be a valid doc.
# Tuned to reject `%PDF-` (5 bytes) and other trivially-truncated inputs
# while still permitting the smallest plausible real document headers.
MIN_UPLOAD_BYTES: Final[int] = 32


def _max_upload_bytes() -> int:
    raw = os.environ.get(MAX_UPLOAD_BYTES_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        v = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return v if v > 0 else DEFAULT_MAX_UPLOAD_BYTES


# --- Magic-byte signatures ---------------------------------------------------

_PDF_MAGIC: Final[bytes] = b"%PDF-"
_ZIP_MAGIC: Final[bytes] = b"PK\x03\x04"          # .docx (also .xlsx/.pptx)
_OLE2_MAGIC: Final[bytes] = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"  # legacy .doc, encrypted Office

# Needles peeked in the first 8 KiB of a ZIP-wrapped file to distinguish
# .docx from .xlsx / .pptx / generic .zip.
_DOCX_INNER_MARKERS: Final[tuple[bytes, ...]] = (
    b"word/document.xml",
    b"word/_rels/document.xml.rels",
)

FileKind = Literal["pdf", "docx", "doc", "unknown"]

# Only these kinds are accepted into the intake pipeline.
ALLOWED_KINDS: Final[frozenset] = frozenset({"pdf", "docx"})


@dataclass(frozen=True)
class SniffResult:
    kind: FileKind
    confident: bool
    reason: str


# --- Public helpers ----------------------------------------------------------


def check_size(data: bytes) -> None:
    """
    Raises DocumentSizeError when `data` is empty, below MIN_UPLOAD_BYTES,
    or above the configured ceiling.
    """
    n = 0 if data is None else len(data)
    if n < MIN_UPLOAD_BYTES:
        raise DocumentSizeError(
            "document is empty or too small",
            detail={"size": n, "min": MIN_UPLOAD_BYTES},
        )
    ceiling = _max_upload_bytes()
    if n > ceiling:
        raise DocumentSizeError(
            "document exceeds maximum size",
            detail={"size": n, "max": ceiling},
        )


def sniff_file_kind(data: bytes) -> SniffResult:
    """
    Identify file format from leading bytes. Never trusts extension /
    claimed MIME type. Returns SniffResult(kind, confident, reason).

    - PDF: leading `%PDF-` → kind='pdf', confident=True
    - ZIP: leading `PK\\x03\\x04`; peek first 8 KiB for a docx-only marker.
      Matches → kind='docx', confident=True. No match → kind='unknown'
      (could be xlsx / pptx / plain zip — not accepted either way).
    - OLE2: leading compound-file header → kind='doc', confident=True.
      This is legacy Word or, more commonly in an HR upload, an
      encrypted .docx masquerading as a compound file.
    - Otherwise → kind='unknown'.
    """
    if not data:
        return SniffResult("unknown", False, "empty payload")
    head = data[:8]
    if head.startswith(_PDF_MAGIC):
        return SniffResult("pdf", True, "magic=%PDF-")
    if head.startswith(_ZIP_MAGIC):
        head_ext = data[:8192]
        if any(m in head_ext for m in _DOCX_INNER_MARKERS):
            return SniffResult("docx", True, "zip+word/document.xml")
        return SniffResult("unknown", False, "zip container but not docx")
    if head.startswith(_OLE2_MAGIC):
        return SniffResult("doc", True, "magic=OLE2 (legacy or encrypted office)")
    return SniffResult("unknown", False, "no known signature")


def _pdf_is_encrypted(data: bytes) -> bool:
    """
    Open the PDF with pdfplumber and classify encryption errors.

    Raises IntakePipelineUnavailableError if pdfplumber is not importable —
    fail-closed. Previously returned False silently on ImportError, which
    meant a missing pdfplumber (drifted venv, removed requirement, etc.)
    let every encrypted PDF pass the gate as "not encrypted". The recipe
    rejected that pattern explicitly; see PARITY-BUG-1 in the audit report.
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:
        raise IntakePipelineUnavailableError(
            "PDF intake dependency missing: pdfplumber is not installed. "
            "Cannot verify encryption status; refusing upload.",
            detail={"missing_package": "pdfplumber"},
        ) from exc
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            _ = pdf.metadata
            if pdf.pages:
                pdf.pages[0].extract_text()
            return False
    except Exception as ex:
        # PARITY-BUG-2: recent pdfminer.six versions raise
        # PdfminerException(PDFPasswordIncorrect()) where str(ex) is empty
        # and only the wrapped inner exception carries the "password" hint.
        # Previously we matched on str(ex)/type name alone and let encrypted
        # PDFs through. Walk repr, class-name chain, and args/causes so the
        # password signal survives exception wrapping across library versions.
        parts: list[str] = [repr(ex), type(ex).__name__]
        for arg in getattr(ex, "args", ()) or ():
            parts.append(repr(arg))
            parts.append(type(arg).__name__)
        cur = ex
        for _ in range(4):  # bounded chain walk
            nxt = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
            if nxt is None or nxt is cur:
                break
            parts.append(repr(nxt))
            parts.append(type(nxt).__name__)
            cur = nxt
        msg = " ".join(p for p in parts if p).lower()
        if "password" in msg or "encrypted" in msg:
            return True
        # Other parse failures are caller-concern (→ MalformedDocumentError);
        # here we only gate on encryption.
        log.info("_pdf_is_encrypted: non-encryption parser error: %s", ex)
        return False


def _docx_is_encrypted(data: bytes) -> bool:
    """
    An encrypted Office file is an OLE2 compound file, NOT a ZIP. If we
    see the OLE2 header on a .docx-named upload, that's the signal.
    A plain ZIP header means not encrypted.
    """
    return data[:8].startswith(_OLE2_MAGIC)


def validate_upload_bytes(data: bytes) -> SniffResult:
    """
    One-call gate for upload endpoints. Runs:
      1. size check  (DocumentSizeError)
      2. magic-byte sniff (UnsupportedFileTypeError when kind not allowed)
      3. encryption check (EncryptedDocumentError — PDF + OLE2-as-docx)

    Returns the SniffResult on success. Raises the appropriate
    PolicyIntakeError subclass on any failure — the API layer maps the
    exception type to an HTTP status.
    """
    check_size(data)
    sniff = sniff_file_kind(data)

    # OLE2 with no other context is most likely an encrypted Office doc
    # (encrypted .docx is OLE2, not ZIP). Surface it as encrypted even
    # though the filename may say .docx.
    if sniff.kind == "doc":
        raise EncryptedDocumentError(
            "document appears to be an encrypted Office package (OLE2)",
            detail={"sniff": {"kind": sniff.kind, "reason": sniff.reason}},
        )

    if sniff.kind not in ALLOWED_KINDS:
        raise UnsupportedFileTypeError(
            f"unsupported file type: {sniff.reason}",
            detail={"sniff": {"kind": sniff.kind, "reason": sniff.reason}},
        )

    if sniff.kind == "pdf" and _pdf_is_encrypted(data):
        raise EncryptedDocumentError(
            "PDF is password-protected",
            detail={"sniff": {"kind": sniff.kind, "reason": sniff.reason}},
        )

    return sniff
