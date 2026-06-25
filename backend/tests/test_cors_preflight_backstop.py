"""Regression: the catch-all OPTIONS backstop must not NameError.

PROD INCIDENT (2026-06-25): `OPTIONS /api/employee/assignments/{id}/intake`
intermittently 500'd with `NameError("name 'Response' is not defined")`. The
B21-CORS backstop handler (`@app.options("/{path:path}")` in backend/main.py)
returns `Response(...)`, but `Response` was not imported. CORSMiddleware handles
most preflights (200); the ones that fall through to the backstop hit the
NameError → 500 with no usable preflight headers → the browser blocks the real
cross-origin GET (hydrate) and PATCH (save), so the intake wizard rendered blank
and never persisted.

A *bare* OPTIONS (no `Access-Control-Request-Method` header) is NOT treated as a
preflight by Starlette's CORSMiddleware, so it falls through to the backstop —
exactly the prod path. These tests exercise both the handler directly and via the
mounted app.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from backend.main import app, cors_preflight_handler  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def _options_request(path: str, origin: str = "https://relopass.com") -> Request:
    return Request(
        {
            "type": "http",
            "method": "OPTIONS",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"origin", origin.encode())],
        }
    )


def test_backstop_handler_does_not_nameerror():
    """Direct call — guards specifically against the `Response` NameError."""
    resp = asyncio.run(
        cors_preflight_handler(
            "api/employee/assignments/abc-123/intake",
            _options_request("/api/employee/assignments/abc-123/intake"),
        )
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-methods")
    assert "Authorization" in resp.headers.get("access-control-allow-headers", "")
    # Allowed origin is echoed back so the browser accepts the preflight.
    assert resp.headers.get("access-control-allow-origin") == "https://relopass.com"


def test_bare_options_preflight_falls_through_to_backstop_200():
    """A bare OPTIONS (no Access-Control-Request-Method) reaches the backstop and
    must return 200 with preflight headers — the exact prod failure path."""
    resp = client.options(
        "/api/employee/assignments/abc-123/intake",
        headers={"Origin": "https://relopass.com"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-methods")
    assert "Authorization" in resp.headers.get("access-control-allow-headers", "")


def test_options_preflight_requires_no_auth():
    """Preflights are never authenticated — no Authorization header, still 200."""
    resp = client.options(
        "/api/employee/assignments/abc-123/intake/submit",
        headers={"Origin": "https://relopass.com"},
    )
    assert resp.status_code == 200
