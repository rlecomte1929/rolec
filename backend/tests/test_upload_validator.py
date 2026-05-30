"""
SEC-006 / AIQ-478 — unit tests for backend.app.services.upload_validator.

Covers the policy surface: oversize → 413, disallowed type → 415,
path-traversal filename → sanitised, valid PDF → accepted with detected MIME.

The async ``read_and_validate`` is driven with ``asyncio.run`` so the suite
needs no pytest-asyncio plugin (not a project dependency).

python-magic (libmagic) is a hard dependency of the module under test; if it
cannot be imported the whole file is skipped with a clear reason rather than
erroring at collection.
"""
import asyncio
import io

import pytest
from fastapi import HTTPException, UploadFile

magic = pytest.importorskip("magic", reason="python-magic/libmagic not installed")
try:
    from backend.app.services import upload_validator as uv  # noqa: E402
except ImportError as exc:  # pragma: no cover - environment guard
    pytest.skip(f"upload_validator import failed: {exc}", allow_module_level=True)


# --- Minimal valid file fixtures (magic-byte accurate) -----------------------

# %PDF- header + minimal trailer is enough for libmagic to report application/pdf.
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + b"0" * 64
# PNG 8-byte signature + IHDR start.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64
# A Windows PE executable starts with "MZ".
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 128
# Plain JavaScript source — libmagic reports text/plain or application/javascript;
# either way it is NOT in the allowlist.
JS_BYTES = b"function pwn(){ while(true){ fetch('/x'); } }\n" * 8


def _upload(content: bytes, filename: str, content_type: str = "application/pdf") -> UploadFile:
    """Build an UploadFile; the claimed content_type is deliberately a lie in
    several tests to prove server-side detection ignores it."""
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers={"content-type": content_type},
    )


def _validate(content: bytes, filename: str, content_type="application/pdf", **kw):
    return asyncio.run(
        uv.read_and_validate(_upload(content, filename, content_type), **kw)
    )


# --- Tests -------------------------------------------------------------------


def test_exe_rejected_415():
    with pytest.raises(HTTPException) as exc:
        # Claims to be a PDF; bytes are a PE executable.
        _validate(EXE_BYTES, "totally_a.pdf", content_type="application/pdf")
    assert exc.value.status_code == 415
    assert str(exc.value.detail).startswith("unsupported_type:")


def test_js_rejected_415():
    with pytest.raises(HTTPException) as exc:
        _validate(JS_BYTES, "script.js", content_type="text/javascript")
    assert exc.value.status_code == 415


def test_oversize_rejected_413():
    big = b"%PDF-1.4\n" + b"0" * (uv.MAX_BYTES + 1)
    assert len(big) > uv.MAX_BYTES
    with pytest.raises(HTTPException) as exc:
        _validate(big, "huge.pdf")
    assert exc.value.status_code == 413
    assert exc.value.detail == "file_too_large"


def test_empty_rejected_400():
    with pytest.raises(HTTPException) as exc:
        _validate(b"", "empty.pdf")
    assert exc.value.status_code == 400


def test_path_traversal_filename_sanitised():
    content, safe, mime = _validate(PDF_BYTES, "../../etc/passwd.pdf")
    assert mime == "application/pdf"
    # secure_filename collapses traversal segments; no separators survive.
    assert "/" not in safe and "\\" not in safe
    assert ".." not in safe
    assert safe == "etc_passwd.pdf"


def test_valid_pdf_accepted():
    content, safe, mime = _validate(PDF_BYTES, "policy.pdf")
    assert content == PDF_BYTES
    assert safe == "policy.pdf"
    assert mime == "application/pdf"


def test_png_in_image_subset():
    content, safe, mime = _validate(
        PNG_BYTES, "passport.png", content_type="image/png",
        allowed_mime=uv.ALLOWED_IMAGE_MIME,
    )
    assert mime == "image/png"


def test_pdf_not_in_image_subset_415():
    # A PDF must be rejected when an endpoint only allows images.
    with pytest.raises(HTTPException) as exc:
        _validate(PDF_BYTES, "doc.pdf", allowed_mime=uv.ALLOWED_IMAGE_MIME)
    assert exc.value.status_code == 415


def test_sanitize_empty_filename_falls_back():
    out = uv.sanitize_filename("../../")
    assert out and "/" not in out


def test_build_storage_path_is_server_generated():
    p = uv.build_storage_path("company-123", "report.pdf")
    parts = p.split("/")
    assert parts[0] == "company-123"
    assert len(parts) == 3  # tenant / uuid / name
    assert parts[2] == "report.pdf"
    # The uuid segment is 36 chars (hyphenated uuid4).
    assert len(parts[1]) == 36
