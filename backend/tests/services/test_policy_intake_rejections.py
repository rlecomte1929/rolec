"""
§9 R1–R4 rejection surface tests — REMEDIATION_PATCHES.md §4 shapes.

R1 — UnsupportedFileTypeError (HTTP 415)
R2 — MalformedDocumentError  (HTTP 422)
R3 — EncryptedDocumentError  (HTTP 422) for PDF + OLE2-as-docx
R4 — DocumentSizeError       (HTTP 413 / empty / too small / too large)

Also covers the DOCX inner-marker check (xlsx renamed .docx → R1) and
OLE2 encrypted-docx detection.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import process_uploaded_document  # noqa: E402
from backend.services.policy_filetype import (  # noqa: E402
    SniffResult,
    sniff_file_kind,
    validate_upload_bytes,
)
from backend.services.policy_intake_errors import (  # noqa: E402
    DocumentSizeError,
    EncryptedDocumentError,
    MalformedDocumentError,
    PolicyIntakeError,
    UnsupportedFileTypeError,
)

_FIXTURES = Path(_REPO_ROOT) / ".audit_tmp" / "fixtures" / "source_docx"

# Plain-text payload long enough to pass the MIN_UPLOAD_BYTES check (32 bytes)
# so R1 fires instead of R4.
_LONG_PLAIN_TEXT = b"this is a harmless plain text document that is not a policy file at all"


# --- R1 ---------------------------------------------------------------------

class TestR1UnsupportedFileType:
    def test_plain_text_rejected(self) -> None:
        with pytest.raises(UnsupportedFileTypeError) as excinfo:
            validate_upload_bytes(_LONG_PLAIN_TEXT)
        assert excinfo.value.code == "UNSUPPORTED_FILE_TYPE"

    def test_xlsx_renamed_docx_rejected(self) -> None:
        """
        XLSX is also a ZIP. The sniff peeks for `word/document.xml` — which
        an xlsx won't carry — so this must surface R1 even though the ZIP
        magic matches.
        """
        fake_xlsx = b"PK\x03\x04" + (b"xl/workbook.xml" + b"\x00" * 8000)
        with pytest.raises(UnsupportedFileTypeError) as excinfo:
            validate_upload_bytes(fake_xlsx)
        assert "not docx" in str(excinfo.value).lower() or excinfo.value.code == "UNSUPPORTED_FILE_TYPE"

    def test_process_uploaded_document_rejects_plain_text(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            process_uploaded_document(_LONG_PLAIN_TEXT, "application/pdf", "x.txt")

    def test_sniff_recognizes_real_docx(self) -> None:
        src = _FIXTURES / "HR_Policy_Dummy_1.docx"
        if not src.exists():
            pytest.skip(f"source fixture missing: {src}")
        result = sniff_file_kind(src.read_bytes())
        assert result.kind == "docx"
        assert result.confident is True

    def test_sniff_recognizes_minimal_pdf(self) -> None:
        result = sniff_file_kind(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"\x00" * 64)
        assert result.kind == "pdf"
        assert result.confident is True


# --- R2 ---------------------------------------------------------------------

class TestR2Malformed:
    def test_truncated_pdf_sniffs_then_fails_parse(self) -> None:
        payload = b"%PDF-1.4\n" + b"\x00" * 128  # truncated, no xref table
        assert sniff_file_kind(payload).kind == "pdf"
        with pytest.raises(MalformedDocumentError):
            process_uploaded_document(payload, "application/pdf", "x.pdf")

    def test_truncated_docx(self) -> None:
        # Enough for sniff to call it docx, too short to parse.
        corrupted = b"PK\x03\x04" + b"word/document.xml" + b"\x00" * 100
        with pytest.raises(MalformedDocumentError):
            process_uploaded_document(
                corrupted,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "x.docx",
            )


# --- R3 ---------------------------------------------------------------------

class TestR3Encrypted:
    def test_ole2_docx_rejected_as_encrypted(self) -> None:
        """
        An OLE2 compound-file header on a `.docx`-named upload is the
        classic encrypted Office package signal.
        """
        ole2 = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 1024
        with pytest.raises(EncryptedDocumentError) as excinfo:
            validate_upload_bytes(ole2)
        assert excinfo.value.code == "ENCRYPTED_DOCUMENT"

    def test_encrypted_pdf_rejected_when_qpdf_available(self) -> None:
        """
        Builds an encrypted fixture at test time via qpdf. Skipped with a
        clear reason when qpdf isn't on the host (Prompt 0 GAP-011).
        """
        import shutil
        import subprocess

        if shutil.which("qpdf") is None:
            pytest.skip("qpdf not installed (Prompt 0 GAP-011). Install via: brew install qpdf")
        sample = Path(_REPO_ROOT) / "docs" / "samples" / "Long Term Assignment Policy Summary.pdf"
        if not sample.exists():
            pytest.skip(f"no sample PDF at {sample}")
        out = Path(_REPO_ROOT) / ".audit_tmp" / "fixtures" / "encrypted_tmp" / "sample.encrypted.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(
            ["qpdf", "--encrypt", "user_pw", "owner_pw", "256", "--", str(sample), str(out)],
            capture_output=True,
        )
        if res.returncode != 0:
            pytest.skip(f"qpdf failed: {res.stderr.decode(errors='ignore')[:200]}")
        with pytest.raises(EncryptedDocumentError) as excinfo:
            validate_upload_bytes(out.read_bytes())
        assert excinfo.value.code == "ENCRYPTED_DOCUMENT"


# --- R4 ---------------------------------------------------------------------

class TestR4Size:
    def test_empty_raises(self) -> None:
        with pytest.raises(DocumentSizeError) as excinfo:
            validate_upload_bytes(b"")
        assert excinfo.value.code == "DOCUMENT_SIZE_INVALID"

    def test_tiny_pdf_header_rejected_as_too_small(self) -> None:
        """
        `%PDF-` alone is 5 bytes — below MIN_UPLOAD_BYTES. Per recipe this
        must rasise DocumentSizeError before the sniff even runs.
        """
        with pytest.raises(DocumentSizeError):
            validate_upload_bytes(b"%PDF-")

    def test_too_large(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RELOPASS_POLICY_UPLOAD_MAX_BYTES", "1024")
        # Valid-looking PDF header + padding past the ceiling.
        payload = b"%PDF-1.4\n" + b"\x00" * 2048
        with pytest.raises(DocumentSizeError):
            validate_upload_bytes(payload)

    def test_process_uploaded_document_rejects_empty(self) -> None:
        with pytest.raises(DocumentSizeError):
            process_uploaded_document(b"", "application/pdf", "x.pdf")


# --- Error shape / quality --------------------------------------------------

class TestErrorShape:
    def test_all_errors_subclass_base(self) -> None:
        for cls in (
            UnsupportedFileTypeError,
            MalformedDocumentError,
            EncryptedDocumentError,
            DocumentSizeError,
        ):
            assert issubclass(cls, PolicyIntakeError)

    def test_detail_kwarg_supported(self) -> None:
        e = UnsupportedFileTypeError("nope", detail={"sniff": {"kind": "unknown"}})
        assert e.detail == {"sniff": {"kind": "unknown"}}
        assert str(e) == "nope"

    def test_no_secrets_in_error_messages(self) -> None:
        for payload, cls in (
            (b"", DocumentSizeError),
            (_LONG_PLAIN_TEXT, UnsupportedFileTypeError),
        ):
            try:
                validate_upload_bytes(payload)
            except cls as e:
                m = str(e).lower()
                for banned in ("password=", "/users/", "postgresql://", "sqlite:///",
                               "openai_api_key", "service_role"):
                    assert banned not in m
            else:
                pytest.fail(f"expected {cls.__name__} for len={len(payload)}")


# --- SniffResult dataclass --------------------------------------------------

class TestSniffResult:
    def test_returns_dataclass(self) -> None:
        r = sniff_file_kind(b"%PDF-1.4\n" + b"\x00" * 32)
        assert isinstance(r, SniffResult)
        assert r.kind == "pdf"
        assert r.confident is True
        assert "pdf" in r.reason.lower()

    def test_unknown_on_empty(self) -> None:
        r = sniff_file_kind(b"")
        assert r.kind == "unknown"
        assert r.confident is False

    def test_ole2_signature(self) -> None:
        r = sniff_file_kind(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 64)
        assert r.kind == "doc"
        assert r.confident is True
