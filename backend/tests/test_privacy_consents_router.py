"""PRIV-005 / AIQ-473 — privacy-notice acknowledgement endpoints.

Verifies the Art. 13 consent endpoints are registered on the *prod* app
(backend.main:app — both registrations, per the dual-layer rule) and that they
are auth-gated. The insert/RLS round-trip is validated separately against real
Postgres (sqlite can't model the `public.` schema prefix or RLS); these tests
guard the wiring, which is exactly what the AI-002 incident class regresses on.
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


def test_routes_registered_on_prod_app():
    paths = {r.path for r in app.routes}
    # Single path serves both POST (record) and GET (status).
    assert "/api/privacy/consents" in paths


def test_post_requires_auth():
    client = TestClient(app)
    resp = client.post(
        "/api/privacy/consents",
        json={"notice_version": "2026-06-03-v1.0", "context": "onboarding"},
    )
    assert resp.status_code == 401, resp.text


def test_get_requires_auth():
    client = TestClient(app)
    resp = client.get("/api/privacy/consents?notice_version=2026-06-03-v1.0")
    assert resp.status_code == 401, resp.text
