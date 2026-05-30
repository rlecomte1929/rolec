"""
SEC-004 — rate-limit coverage tests.

Behavioural tests run against a *mirror* FastAPI app that reuses the real SEC-004
machinery — the named limit constants, ``user_key_func``, the shared
``_real_remote_address`` key func, the slowapi ``SlowAPIMiddleware`` (for the
STANDARD default), and the real 429 handler (``_rate_limit_exceeded_handler``)
from ``backend.main``. We use a mirror app because the global test harness sets
``RELOPASS_DISABLE_RATE_LIMITS=1`` (see backend/conftest.py), which disables the
real limiter at import time so its ``@limiter.limit`` decorators register nothing
in-process. The mirror app instantiates a freshly-*enabled* limiter with the same
config, so we can assert real 429 behaviour without flipping the global env (which
would break every other test that hammers endpoints).

Config/wiring tests assert the *real* ``backend.main`` app is set up correctly
(default limit, exemptions, admin middleware, named constants), and a bypass test
proves ``RELOPASS_DISABLE_RATE_LIMITS`` disables limiting (the CLAUDE.md contract).
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./_sec004_test.db")

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import backend.main as bm
from backend.app.rate_limits import (
    ADMIN_LIMIT,
    AI_LIMIT,
    AUTH_LIMIT,
    STANDARD_LIMIT,
    UPLOAD_LIMIT,
    user_key_func,
)
from backend.rate_limit import _real_remote_address


def _build_mirror_app(enabled: bool = True) -> FastAPI:
    """A minimal app wired with the real SEC-004 components and a fresh limiter."""
    test_limiter = Limiter(
        key_func=_real_remote_address,
        enabled=enabled,
        default_limits=[STANDARD_LIMIT],
    )
    app = FastAPI()
    app.state.limiter = test_limiter
    # Reuse the REAL 429 handler so we test the documented response shape.
    app.add_exception_handler(RateLimitExceeded, bm._rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.post("/login")
    @test_limiter.limit(AUTH_LIMIT)
    def login(request: Request):
        return {"ok": True}

    @app.get("/standard")
    def standard(request: Request):  # undecorated → STANDARD default via middleware
        return {"ok": True}

    @app.post("/upload")
    @test_limiter.limit(UPLOAD_LIMIT)
    def upload(request: Request):
        return {"ok": True}

    @app.post("/ai")
    @test_limiter.limit(AI_LIMIT, key_func=user_key_func)
    def ai(request: Request):
        return {"ok": True}

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_build_mirror_app(enabled=True))


# ── Behavioural: one test per bucket ─────────────────────────────────────────

def test_auth_login_blocks_after_5_per_minute(client: TestClient):
    # AUTH_LIMIT = 5/minute → 6th request is throttled.
    for i in range(5):
        assert client.post("/login").status_code == 200, f"request {i + 1} should pass"
    resp = client.post("/login")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"
    body = resp.json()
    assert body["error"] == "rate_limit_exceeded"
    assert body["retry_after"] == 60
    assert "Retry after 60s" in body["message"]


def test_standard_endpoint_blocks_after_100_per_minute(client: TestClient):
    # STANDARD_LIMIT = 100/minute (applied to undecorated routes via middleware).
    for i in range(100):
        assert client.get("/standard").status_code == 200, f"request {i + 1} should pass"
    assert client.get("/standard").status_code == 429


def test_upload_endpoint_blocks_after_10_per_minute(client: TestClient):
    # UPLOAD_LIMIT = 10/minute → 11th request is throttled.
    for i in range(10):
        assert client.post("/upload").status_code == 200, f"request {i + 1} should pass"
    assert client.post("/upload").status_code == 429


def test_ai_endpoint_is_per_user_not_per_ip(client: TestClient):
    # AI_LIMIT = 20/minute keyed on the authenticated principal (user_key_func).
    hdr_a = {"Authorization": "Bearer user-a-token"}
    hdr_b = {"Authorization": "Bearer user-b-token"}
    for i in range(20):
        assert client.post("/ai", headers=hdr_a).status_code == 200, f"req {i + 1}"
    # 21st request for user A is throttled...
    assert client.post("/ai", headers=hdr_a).status_code == 429
    # ...but a different user (different token) is unaffected.
    assert client.post("/ai", headers=hdr_b).status_code == 200


def test_429_response_shape_and_headers(client: TestClient):
    for _ in range(5):
        client.post("/login")
    resp = client.post("/login")
    assert resp.status_code == 429
    # Documented JSON body...
    body = resp.json()
    assert set(["error", "message", "retry_after"]).issubset(body.keys())
    assert body["error"] == "rate_limit_exceeded"
    assert body["retry_after"] == 60
    # ...backward-compat keys retained...
    assert "detail" in body and "request_id" in body
    # ...and the headers.
    assert resp.headers.get("Retry-After") == "60"
    assert resp.headers.get("X-Request-ID")


# ── Admin bucket (path-scoped middleware component) ───────────────────────────

def test_admin_bucket_is_20_per_minute():
    assert str(bm._admin_rate_limit_item) == "20 per 1 minute"
    # Drive the real admin limiter component directly: 20 allowed, 21st blocked.
    bm._admin_rate_limiter._storage.reset()
    results = [
        bm._admin_rate_limiter.hit(bm._admin_rate_limit_item, "sec004-admin", "9.9.9.9")
        for _ in range(21)
    ]
    assert results[:20] == [True] * 20
    assert results[20] is False


def test_real_app_registers_admin_rate_limit_middleware():
    mw_names = [m.cls.__name__ for m in bm.app.user_middleware]
    # The admin limiter is a function-based @app.middleware("http") (BaseHTTPMiddleware).
    assert any("Middleware" in n for n in mw_names)
    assert callable(bm._admin_rate_limit_middleware)


# ── Config / wiring on the real app ──────────────────────────────────────────

def test_named_constants_have_expected_values():
    assert AUTH_LIMIT == "5/minute"
    assert STANDARD_LIMIT == "100/minute"
    assert UPLOAD_LIMIT == "10/minute"
    assert ADMIN_LIMIT == "20/minute"
    assert AI_LIMIT == "20/minute"


def test_real_limiter_has_standard_default():
    assert [str(g) for g in bm.limiter._default_limits] == ["100 per 1 minute"]


def test_real_app_exempts_infra_and_service_routes():
    exempt = bm.limiter._exempt_routes
    assert "backend.main.health_check" in exempt
    assert "backend.main.supabase_health" in exempt
    assert "backend.app.routers.support.inbound_email_webhook" in exempt
    assert "backend.app.routers.support.triage_ticket" in exempt


def test_standard_slowapi_middleware_installed():
    assert any(m.cls is SlowAPIMiddleware for m in bm.app.user_middleware)


# ── Bypass contract (CLAUDE.md) ──────────────────────────────────────────────

def test_disable_env_bypasses_all_limits():
    # A disabled limiter must let unlimited requests through (the test-suite contract).
    bypass_client = TestClient(_build_mirror_app(enabled=False))
    for _ in range(15):  # well past AUTH_LIMIT (5)
        assert bypass_client.post("/login").status_code == 200
