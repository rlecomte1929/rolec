"""EMPLOYEE login must not block on a stuck reconcile path."""
from __future__ import annotations

import os
import sys
import threading
import time
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.routers import auth as auth_router  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services.assignment_claim_link_service import ClaimLinkResult  # noqa: E402

client = TestClient(app)


def test_employee_login_returns_when_reconcile_hangs(monkeypatch):
    """If reconcile blocks past the timeout, login still returns 200 promptly."""
    # Register a fresh EMPLOYEE so the test is self-contained and doesn't
    # depend on seed data.
    email = f"emp-{uuid.uuid4().hex[:10]}@example.test"
    password = "Passw0rd!"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": "EMPLOYEE", "name": "T"},
    )
    assert reg.status_code == 200, reg.text

    started = threading.Event()
    release = threading.Event()

    def _blocking_reconcile(*_args, **_kwargs):
        started.set()
        # Block well past the timeout; released after the assertions so the
        # executor thread can exit without leaking past the test.
        release.wait(timeout=30)
        return ClaimLinkResult()

    monkeypatch.setattr(
        auth_router, "reconcile_pending_assignment_claims", _blocking_reconcile
    )
    monkeypatch.setattr(auth_router, "_RECONCILE_TIMEOUT_SECONDS", 0.5)

    t0 = time.perf_counter()
    res = client.post(
        "/api/auth/login",
        json={"identifier": email, "password": password},
    )
    elapsed = time.perf_counter() - t0
    release.set()

    assert started.is_set(), "reconcile was never invoked"
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("token")
    assert body.get("user", {}).get("role") == "EMPLOYEE"
    assert body.get("reconciliation") is None
    # Timeout is 0.5s plus FastAPI/serialization overhead.
    # 5s is generous and still proves we're not blocking on reconcile.
    assert elapsed < 5.0, f"login took {elapsed:.2f}s — timeout not enforced"
