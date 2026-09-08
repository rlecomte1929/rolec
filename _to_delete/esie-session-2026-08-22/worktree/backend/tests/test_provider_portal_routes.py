"""H2 — provider portal route registration + auth smoke tests.

Regression guard for the shipped-but-unregistered surface: until H2,
``backend/app/routers/provider_portal.py`` defined /api/provider/tasks,
/api/provider/tasks/{id}, /api/provider/case-summary and /api/provider/profile
but was registered in NEITHER backend/main.py NOR backend/app/main.py, so every
route 404'd in production while the frontend (providerPortal.ts → ProviderPortal.tsx)
actively called them.

These tests mount the PROD app (``backend.main:app`` — the instance Render boots)
and assert, per route:
  * non-404  → the route is actually registered (the H2 fix), and
  * 401 without / with a bad Bearer → ``require_provider_jwt`` guards it.

The auth dependency fires before any handler/DB code, so no live DB is needed.
The public ``/api/provider/auth/verify`` (served by providers.py, already
registered in prod) is also smoke-checked since providerPortal.ts depends on it.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402  (the prod entrypoint Render boots)

client = TestClient(app)

# provider_portal routes that must be reachable + guarded (method, path)
_PORTAL_ROUTES = [
    ("GET", "/api/provider/tasks"),
    ("PATCH", "/api/provider/tasks/some-task-id"),
    ("GET", "/api/provider/case-summary"),
    ("PATCH", "/api/provider/profile"),
]


def test_provider_portal_routes_registered_in_prod_app():
    """All provider_portal paths must be present in the prod app (not 404)."""
    paths = {r.path for r in app.routes}
    for expected in (
        "/api/provider/tasks",
        "/api/provider/tasks/{task_id}",
        "/api/provider/case-summary",
        "/api/provider/profile",
    ):
        assert expected in paths, f"{expected} not registered in backend.main app"


def test_portal_routes_not_404_and_require_auth():
    """Without a Bearer token each route returns 401 (guarded), never 404 (dead)."""
    for method, path in _PORTAL_ROUTES:
        resp = client.request(method, path, json={})
        assert resp.status_code != 404, f"{method} {path} is dead (404) — not registered"
        assert resp.status_code == 401, (
            f"{method} {path} should require a provider token (401), got {resp.status_code}"
        )


def test_portal_routes_reject_bad_bearer():
    """A malformed/invalid provider token is rejected with 401."""
    headers = {"Authorization": "Bearer not-a-real-jwt"}
    for method, path in _PORTAL_ROUTES:
        resp = client.request(method, path, headers=headers, json={})
        assert resp.status_code == 401, (
            f"{method} {path} should 401 on a bad token, got {resp.status_code}"
        )


def test_auth_verify_endpoint_is_public_and_reachable():
    """providerPortal.ts calls GET /api/provider/auth/verify (served by providers.py).

    It is intentionally public and returns {valid: false} for a bad token
    rather than 404/401 — proves the frontend's pre-portal token check works.
    """
    resp = client.get("/api/provider/auth/verify", params={"token": "bad-token"})
    assert resp.status_code == 200, resp.text
    assert resp.json().get("valid") is False
