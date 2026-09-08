"""
SEC-005: the security-headers middleware must stamp all six headers on every API
response. We probe the unauthenticated /health route (rate-limit-exempt, no DB
auth) and assert the exact header values, plus that the API CSP is locked down to
deny-everything (the JSON API renders no pages and loads no resources).

Mounts the real production app (backend.main:app) so the test fails if the
middleware is registered only on the modular app/ instance — the same dual-layer
trap documented in backend/CLAUDE.md.
"""
from __future__ import annotations

import os

# Keep the app-mounted harness quiet: no rate limits, no query-counter noise.
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)

EXPECTED_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def test_security_headers_present_on_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    for name, value in EXPECTED_HEADERS.items():
        assert resp.headers.get(name) == value, f"{name} missing or wrong"


def test_security_headers_present_on_error_response():
    # Headers must apply to every response, including error paths (middleware runs
    # regardless of status). A bogus path resolves to an error status, not 200.
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code >= 400
    for name in EXPECTED_HEADERS:
        assert name in resp.headers, f"{name} missing on error response"


def test_cors_preflight_unaffected():
    # SEC-005 must not change CORS behavior: an allowed-origin OPTIONS preflight
    # still gets its Access-Control-Allow-* headers.
    resp = client.options(
        "/health",
        headers={
            "Origin": "https://relopass.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("Access-Control-Allow-Origin") == "https://relopass.com"
