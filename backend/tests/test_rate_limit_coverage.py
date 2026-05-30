"""
SEC-004 — rate-limit coverage tests.

Design notes:
* The policy (named buckets, path matching, 429 body/headers) lives in
  backend.app.rate_limits, which is import-safe (no app, no DB). These tests import
  it directly — no need to import backend.main, which the test harness can't import
  at module level because backend/conftest.py mocks backend.database.
* AUTH (5/min) and STANDARD (100/min) ride slowapi (decorator + SlowAPIMiddleware
  default). We exercise them against a *mirror* app with a freshly-enabled limiter,
  because the harness sets RELOPASS_DISABLE_RATE_LIMITS=1, disabling the real limiter
  at import time (flipping the global env would break other tests). The mirror's 429
  handler reuses the real rate_limit_payload()/rate_limit_headers() builders.
* UPLOAD/ADMIN/AI ride a path-scoped middleware whose logic is the pure function
  rate_limits.path_limit — unit-tested directly.
* A subprocess test boots backend.main with the limiter ENABLED (the production
  condition) to guard against the slowapi "param must be named request" crash.
"""
from __future__ import annotations

import os
import subprocess
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./_sec004_test.db")

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.app.rate_limits import (
    ADMIN_LIMIT,
    AI_LIMIT,
    AUTH_LIMIT,
    STANDARD_LIMIT,
    UPLOAD_LIMIT,
    UPLOAD_PATHS,
    is_ai_path,
    path_limit,
    rate_limit_headers,
    rate_limit_payload,
    reset_path_limit_storage,
)
from backend.rate_limit import _real_remote_address
from backend.rate_limit import limiter as real_limiter

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── slowapi buckets (AUTH + STANDARD): behavioural via a mirror app ───────────

def _build_mirror_app(enabled: bool = True) -> FastAPI:
    test_limiter = Limiter(
        key_func=_real_remote_address,
        enabled=enabled,
        default_limits=[STANDARD_LIMIT],
    )
    app = FastAPI()
    app.state.limiter = test_limiter

    def _handler(request: Request, exc: RateLimitExceeded):
        # Reuse the REAL 429 body + headers builders (the documented shape).
        return JSONResponse(
            status_code=429, content=rate_limit_payload(), headers=rate_limit_headers()
        )

    app.add_exception_handler(RateLimitExceeded, _handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.post("/login")
    @test_limiter.limit(AUTH_LIMIT)
    def login(request: Request):
        return {"ok": True}

    @app.get("/standard")  # undecorated → STANDARD default via middleware
    def standard(request: Request):
        return {"ok": True}

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_build_mirror_app(enabled=True))


def test_auth_login_blocks_after_5_per_minute(client: TestClient):
    for i in range(5):
        assert client.post("/login").status_code == 200, f"request {i + 1} should pass"
    resp = client.post("/login")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"


def test_standard_endpoint_blocks_after_100_per_minute(client: TestClient):
    for i in range(100):
        assert client.get("/standard").status_code == 200, f"request {i + 1} should pass"
    assert client.get("/standard").status_code == 429


def test_429_response_shape_and_headers(client: TestClient):
    for _ in range(5):
        client.post("/login")
    resp = client.post("/login")
    assert resp.status_code == 429
    body = resp.json()
    assert {"error", "message", "retry_after"}.issubset(body.keys())
    assert body["error"] == "rate_limit_exceeded"
    assert body["retry_after"] == 60
    assert "Retry after 60s" in body["message"]
    assert "detail" in body  # back-compat key
    assert resp.headers.get("Retry-After") == "60"


def test_disable_env_bypasses_all_limits():
    bypass = TestClient(_build_mirror_app(enabled=False))
    for _ in range(15):  # well past AUTH_LIMIT (5)
        assert bypass.post("/login").status_code == 200


# ── middleware buckets (UPLOAD / ADMIN / AI): unit-test the pure helper ───────

@pytest.fixture()
def fresh_buckets():
    reset_path_limit_storage()
    yield
    reset_path_limit_storage()


def _drive(path: str, n: int, ip: str = "1.2.3.4", user_key: str = "user-a"):
    reset_path_limit_storage()
    return [path_limit(path, ip, user_key) for _ in range(n)]


def test_upload_path_blocks_after_10_per_minute(fresh_buckets):
    res = _drive("/api/hr/policies/upload", 12)
    assert all(x is None for x in res[:10]), "first 10 uploads allowed"
    assert res[10] is not None, "11th upload throttled"


def test_admin_path_blocks_after_20_per_minute(fresh_buckets):
    res = _drive("/api/admin/companies", 22)
    assert all(x is None for x in res[:20]), "first 20 admin calls allowed"
    assert res[20] is not None, "21st admin call throttled"


def test_ai_path_blocks_after_20(fresh_buckets):
    res = _drive("/api/policies/abc123/extract", 22)
    assert all(x is None for x in res[:20]), "first 20 AI calls allowed"
    assert res[20] is not None, "21st AI call throttled"


def test_ai_bucket_is_per_user_not_per_ip(fresh_buckets):
    for _ in range(20):
        path_limit("/api/guidance/generate", "9.9.9.9", "tok-a")
    # 21st for user A throttled...
    assert path_limit("/api/guidance/generate", "9.9.9.9", "tok-a") is not None
    # ...different user (same IP) unaffected.
    assert path_limit("/api/guidance/generate", "9.9.9.9", "tok-b") is None


def test_bucket_precedence():
    # /api/admin/policies/upload is an UPLOAD route, not the ADMIN bucket.
    assert not is_ai_path("/api/admin/policies/upload")
    assert "/api/admin/policies/upload" in UPLOAD_PATHS
    # /api/admin/policies/{id}/extract is an AI route, not the ADMIN bucket.
    assert is_ai_path("/api/admin/policies/doc-1/extract")
    # plain admin path falls through to the ADMIN bucket.
    assert not is_ai_path("/api/admin/companies")
    assert "/api/admin/companies" not in UPLOAD_PATHS


# ── config ────────────────────────────────────────────────────────────────────

def test_named_constants_have_expected_values():
    assert AUTH_LIMIT == "5/minute"
    assert STANDARD_LIMIT == "100/minute"
    assert UPLOAD_LIMIT == "10/minute"
    assert ADMIN_LIMIT == "20/minute"
    assert AI_LIMIT == "20/minute"


def test_real_limiter_has_standard_default():
    # One default-limit group is wired (STANDARD_LIMIT) — applied to undecorated
    # routes by SlowAPIMiddleware. (slowapi wraps it in a LimitGroup, not a plain
    # string, so assert on presence rather than str()-ing the group.)
    assert len(real_limiter._default_limits) == 1


# ── production boot guard (the slowapi "param must be named request" crash) ───

def test_app_imports_with_limiter_enabled():
    """
    backend.main must import cleanly with the limiter ENABLED (production). Run in a
    subprocess so the limiter is enabled at import (the in-process harness disables
    it) and the real DB engine is used (the harness mocks backend.database).
    """
    code = (
        "import os;"
        "os.environ['RELOPASS_DISABLE_RATE_LIMITS']='0';"
        "os.environ.setdefault('DATABASE_URL','sqlite:///./_sec004_boot.db');"
        "import backend.main as m;"
        "print('ENABLED', m.limiter.enabled)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"app failed to import with limits enabled:\n{proc.stderr}"
    assert "ENABLED True" in proc.stdout
