"""
§9 R1–R4 rejection surface tests.

Covers Prompt A §9 and the Prompt 0 GAPs it maps to:
  - R1 encrypted PDF     → EncryptedDocumentError (HTTP 422)
  - R2 corrupt PDF       → MalformedDocumentError (HTTP 422)
  - R3 zero-byte upload  → DocumentSizeError (HTTP 413)
  - R4 wrong MIME        → UnsupportedFileTypeError (HTTP 415)

R1 genuinely needs an encrypted-PDF fixture, which requires qpdf on the
audit host; when the fixture isn't buildable the R1 test is skipped
with a clear reason rather than silently passing.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import process_uploaded_document  # noqa: E402
from backend.services.policy_filetype import (  # noqa: E402
    sniff_file_kind,
    validate_upload_bytes,
)
from backend.services.policy_intake_errors import (  # noqa: E402
    DocumentSizeError,
    EncryptedDocumentError,
    MalformedDocumentError,
    UnsupportedFileTypeError,
)

_FIXTURES = Path(_REPO_ROOT) / ".audit_tmp" / "fixtures" / "source_docx"


class TestR3ZeroByte:
    """Empty-file upload must raise DocumentSizeError mapped to 413."""

    def test_empty_bytes_raises(self) -> None:
        with pytest.raises(DocumentSizeError) as excinfo:
            validate_upload_bytes(b"")
        assert excinfo.value.error_code == "document_too_large"
        assert excinfo.value.http_status == 413

    def test_process_uploaded_document_rejects_empty(self) -> None:
        with pytest.raises(DocumentSizeError):
            process_uploaded_document(b"", "application/pdf", "x.pdf")


class TestR4WrongMIME:
    """
    A file named .docx whose first bytes are neither %PDF- nor a zip
    signature must be rejected with UnsupportedFileTypeError (HTTP 415).
    """

    def test_random_bytes_named_docx_rejected(self) -> None:
        # 16 bytes of random non-magic content; no PK zip header, no %PDF-.
        payload = b"\x00\x00\x00\x00the filename lies"
        with pytest.raises(UnsupportedFileTypeError) as excinfo:
            validate_upload_bytes(payload)
        assert excinfo.value.error_code == "unsupported_file_type"
        assert excinfo.value.http_status == 415

    def test_process_uploaded_document_rejects_wrong_mime(self) -> None:
        payload = b"\x00\x00\x00\x00not a document"
        with pytest.raises(UnsupportedFileTypeError):
            process_uploaded_document(payload, "application/pdf", "x.docx")

    def test_sniff_recognizes_real_docx(self) -> None:
        """Sanity: a real DOCX fixture sniffs as 'docx'."""
        src = _FIXTURES / "HR_Policy_Dummy_1.docx"
        if not src.exists():
            pytest.skip(f"source fixture missing: {src}")
        assert sniff_file_kind(src.read_bytes()) == "docx"

    def test_sniff_recognizes_minimal_pdf(self) -> None:
        """A %PDF-1.4 header is enough to sniff as PDF."""
        assert sniff_file_kind(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3") == "pdf"


class TestR2CorruptPDF:
    """
    A file that sniffs as PDF (starts with %PDF-) but is otherwise
    truncated/garbage triggers MalformedDocumentError (HTTP 422).
    validate_upload_bytes passes the sniff; the parser fails in
    process_uploaded_document, which surfaces it as MalformedDocumentError.
    """

    def test_truncated_pdf_sniffs_then_fails_parse(self) -> None:
        payload = b"%PDF-1.4\n" + b"\x00" * 128  # truncated, no xref table
        # Sniff passes (magic matches).
        assert sniff_file_kind(payload) == "pdf"
        # End-to-end raises MalformedDocumentError from the parser step.
        with pytest.raises(MalformedDocumentError):
            process_uploaded_document(payload, "application/pdf", "x.pdf")


class TestR1EncryptedPDF:
    """
    Encrypted PDF → EncryptedDocumentError (HTTP 422).

    Needs qpdf to construct an encrypted fixture; when absent the test
    skips with a clear reason (Prompt 0 GAP-011).
    """

    def _make_encrypted_pdf_or_skip(self) -> bytes:
        import shutil
        import subprocess
        if shutil.which("qpdf") is None:
            pytest.skip(
                "qpdf not installed on audit host (Prompt 0 GAP-011). "
                "Install via: brew install qpdf"
            )
        # Need a valid text PDF to encrypt. soffice would generate one from
        # a DOCX but is ALSO not required — skip if no sample text PDF is
        # available.
        sample_src = Path(_REPO_ROOT) / "docs" / "samples" / "Long Term Assignment Policy Summary.pdf"
        if not sample_src.exists():
            pytest.skip(f"no sample PDF available at {sample_src}")
        tmpdir = Path(_REPO_ROOT) / ".audit_tmp" / "fixtures" / "encrypted_tmp"
        tmpdir.mkdir(parents=True, exist_ok=True)
        out_path = tmpdir / "sample.encrypted.pdf"
        res = subprocess.run(
            ["qpdf", "--encrypt", "user_pw", "owner_pw", "256", "--",
             str(sample_src), str(out_path)],
            capture_output=True,
        )
        if res.returncode != 0:
            pytest.skip(f"qpdf failed: {res.stderr.decode(errors='ignore')[:200]}")
        return out_path.read_bytes()

    def test_encrypted_pdf_rejected(self) -> None:
        data = self._make_encrypted_pdf_or_skip()
        with pytest.raises(EncryptedDocumentError) as excinfo:
            validate_upload_bytes(data)
        assert excinfo.value.error_code == "encrypted_document"
        assert excinfo.value.http_status == 422


class TestErrorMessageQuality:
    """§9 E1–E3: typed classes, plain messages, no secrets / paths / creds."""

    def test_all_errors_are_typed(self) -> None:
        from backend.services.policy_intake_errors import PolicyIntakeError
        for cls in (DocumentSizeError, UnsupportedFileTypeError,
                    MalformedDocumentError, EncryptedDocumentError):
            assert issubclass(cls, PolicyIntakeError)
            assert issubclass(cls, Exception)

    def test_no_secrets_in_default_messages(self) -> None:
        # Trigger each error and confirm the user-visible string is clean.
        tests = [
            (b"", DocumentSizeError),
            (b"\x00" * 32, UnsupportedFileTypeError),
        ]
        for payload, exc_cls in tests:
            try:
                validate_upload_bytes(payload)
            except exc_cls as e:
                msg = str(e).lower()
                for banned in ("password", "/users/", "postgresql://", "sqlite:///",
                               "openai_api_key", "service_role"):
                    assert banned not in msg, f"banned substring {banned!r} in {msg!r}"
            else:
                pytest.fail(f"expected {exc_cls.__name__} on payload len={len(payload)}")
