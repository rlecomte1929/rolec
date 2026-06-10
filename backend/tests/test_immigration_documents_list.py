"""BL-OCR.4 / AIQ-750 — GET immigration documents list endpoint.

The upload (POST) endpoint shipped in BL-OCR.2; this adds the list (GET) the
employee/HR document viewer reads. Verifies the route is registered on the prod
app and is auth-gated. Row-level access scoping is the shared
_resolve_accessible_case helper (same as POST), so it isn't re-tested here.
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


def test_get_documents_route_registered():
    routes = {(m, r.path) for r in app.routes for m in (getattr(r, "methods", None) or [])}
    assert ("GET", "/api/immigration/cases/{case_id}/documents") in routes


def test_get_documents_requires_auth():
    client = TestClient(app)
    resp = client.get("/api/immigration/cases/case-123/documents")
    assert resp.status_code == 401, resp.text
