"""
SEC-006 / AIQ-478 — endpoint-level validation contract.

The unit tests in test_upload_validator.py prove read_and_validate's policy
(415/413/sanitisation). This file proves the *integration contract*: that when
the validator is wired into a real FastAPI multipart upload route exactly the
way the production endpoints wire it, the raised HTTPException surfaces as the
correct HTTP status to the client (415 / 413 / 200) and the client-supplied
Content-Type is ignored in favour of content-based detection.

This deliberately mounts a minimal app around read_and_validate rather than
importing the 12k-line main.py monolith: the thing under test is the
UploadFile -> read_and_validate -> HTTP status mapping, which is identical for
every endpoint that calls it. Per-endpoint allowlist selection is covered by
the unit tests.

Skips cleanly if python-magic/libmagic is unavailable.
"""
import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

pytest.importorskip("magic", reason="python-magic/libmagic not installed")
try:
    from backend.app.services.upload_validator import (  # noqa: E402
        ALLOWED_IMAGE_MIME,
        read_and_validate,
    )
except ImportError as exc:  # pragma: no cover - environment guard
    pytest.skip(f"upload_validator import failed: {exc}", allow_module_level=True)


PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + b"0" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 128


def _make_app() -> FastAPI:
    """Mirror how production endpoints wire the validator: a doc route (PDF/DOCX
    default allowlist) and an image route (image subset)."""
    app = FastAPI()

    @app.post("/upload/doc")
    async def upload_doc(file: UploadFile = ...):  # noqa: B008
        content, safe, mime = await read_and_validate(file)
        return {"name": safe, "mime": mime, "size": len(content)}

    @app.post("/upload/image")
    async def upload_image(file: UploadFile = ...):  # noqa: B008
        content, safe, mime = await read_and_validate(
            file, allowed_mime=ALLOWED_IMAGE_MIME, max_bytes=10 * 1024 * 1024
        )
        return {"name": safe, "mime": mime, "size": len(content)}

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_make_app())


def test_valid_pdf_returns_200(client: TestClient):
    r = client.post(
        "/upload/doc",
        files={"file": ("policy.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mime"] == "application/pdf"
    assert body["name"] == "policy.pdf"


def test_exe_disguised_as_pdf_returns_415(client: TestClient):
    # Client claims application/pdf; bytes are a PE executable. Server-side
    # detection must win and reject with 415.
    r = client.post(
        "/upload/doc",
        files={"file": ("invoice.pdf", EXE_BYTES, "application/pdf")},
    )
    assert r.status_code == 415, r.text
    assert "unsupported_type" in r.text


def test_oversize_returns_413(client: TestClient):
    big = b"%PDF-1.4\n" + b"0" * (20 * 1024 * 1024 + 1)
    r = client.post(
        "/upload/doc",
        files={"file": ("huge.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413, r.text


def test_path_traversal_filename_sanitised_over_http(client: TestClient):
    r = client.post(
        "/upload/doc",
        files={"file": ("../../etc/passwd.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "etc_passwd.pdf"


def test_image_route_accepts_png(client: TestClient):
    r = client.post(
        "/upload/image",
        files={"file": ("passport.png", PNG_BYTES, "image/png")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["mime"] == "image/png"


def test_image_route_rejects_pdf_415(client: TestClient):
    r = client.post(
        "/upload/image",
        files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code == 415, r.text
