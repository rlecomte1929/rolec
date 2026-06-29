"""AIQ-1148 — POST /api/ocr/process router behaviour.

App-mounted against the PROD app (backend.main) so it also asserts the route is served
there (dual-registration). Auth is overridden; Mistral is monkeypatched (no real API).
"""
from __future__ import annotations

import base64
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
import backend.app.auth_deps as auth_deps  # noqa: E402
import backend.app.routers.ocr as ocr_router  # noqa: E402

# A real 1x1 PNG so the content-based MIME check (python-magic) reliably passes.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAdpDqp8AAAAASUVORK5CYII="
)


def _fake_user():
    return {"id": "u-emp-1", "role": "EMPLOYEE", "is_admin": False, "company": "co-1"}


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[auth_deps.get_current_user] = _fake_user
    monkeypatch.setattr(
        ocr_router,
        "mistral_ocr_document",
        lambda content, mime: {"markdown": "# Receipt\nTotal 50 EUR", "pages_count": 1},
    )
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def test_process_returns_structured_ocr(client):
    r = client.post(
        "/api/ocr/process",
        files={"file": ("receipt.png", _PNG, "image/png")},
        data={"document_type": "expense_receipt"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["raw_markdown"] == "# Receipt\nTotal 50 EUR"
    assert body["pages_count"] == 1
    assert body["extracted_fields"] == {}
    assert body["document_type"] == "expense_receipt"
    assert body["id"]


def test_unsupported_document_type_400(client):
    r = client.post(
        "/api/ocr/process",
        files={"file": ("x.png", _PNG, "image/png")},
        data={"document_type": "nonsense"},
    )
    assert r.status_code == 400


def test_missing_api_key_500(client, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    r = client.post(
        "/api/ocr/process",
        files={"file": ("x.png", _PNG, "image/png")},
        data={"document_type": "generic"},
    )
    assert r.status_code == 500
    assert "MISTRAL_API_KEY" in r.text


def test_empty_file_rejected(client):
    r = client.post(
        "/api/ocr/process",
        files={"file": ("x.png", b"", "image/png")},
        data={"document_type": "generic"},
    )
    assert r.status_code in (400, 422)
