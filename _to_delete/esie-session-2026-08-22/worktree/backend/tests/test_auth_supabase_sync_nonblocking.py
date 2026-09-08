"""Login/register must not block on a slow Supabase Auth admin call.

Regression test for the "Request timed out" error users saw on
https://relopass.com/auth?mode=login: the previous implementation called
`sync_relopass_user_to_supabase_auth` synchronously inside the request path,
so a wedged Supabase admin API would hold the response past the frontend's
45s axios timeout. The fix dispatches the sync to a background pool.
"""
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
from backend.database import db as _legacy_db  # noqa: E402
from backend.main import app  # noqa: E402

# The legacy DB instance initializes lazily on first _exec, but several read
# paths (get_user_by_email, ...) bypass that. Force schema creation up front
# so these tests run cleanly under a fresh SQLite file.
_legacy_db.ensure_initialized()

client = TestClient(app)


def test_login_returns_when_supabase_sync_hangs(monkeypatch):
    email = f"sup-{uuid.uuid4().hex[:10]}@example.test"
    password = "Passw0rd!"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": "EMPLOYEE", "name": "T"},
    )
    assert reg.status_code == 200, reg.text

    invoked = threading.Event()
    release = threading.Event()

    def _hanging_sync(*_args, **_kwargs):
        invoked.set()
        # Block well past the frontend's 45s axios cap; released at end of
        # test so the background thread can exit cleanly.
        release.wait(timeout=60)
        return True

    # Patch the symbol the dispatcher imports lazily.
    import backend.app.services.supabase_auth_sync as sync_mod

    monkeypatch.setattr(sync_mod, "sync_relopass_user_to_supabase_auth", _hanging_sync)

    t0 = time.perf_counter()
    res = client.post(
        "/api/auth/login",
        json={"identifier": email, "password": password},
    )
    elapsed = time.perf_counter() - t0
    release.set()

    assert res.status_code == 200, res.text
    assert res.json().get("token")
    # If the sync were still in-band, this would take >60s (release.wait).
    # 5s is generous and still proves the dispatch is non-blocking.
    assert elapsed < 5.0, f"login took {elapsed:.2f}s — Supabase sync is blocking"
    # The dispatch should have queued the sync onto the background pool.
    assert invoked.wait(timeout=5.0), "background Supabase sync was never invoked"


def test_register_returns_when_supabase_sync_hangs(monkeypatch):
    email = f"sup-reg-{uuid.uuid4().hex[:10]}@example.test"
    password = "Passw0rd!"

    invoked = threading.Event()
    release = threading.Event()

    def _hanging_sync(*_args, **_kwargs):
        invoked.set()
        release.wait(timeout=60)
        return True

    import backend.app.services.supabase_auth_sync as sync_mod

    monkeypatch.setattr(sync_mod, "sync_relopass_user_to_supabase_auth", _hanging_sync)

    t0 = time.perf_counter()
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": "EMPLOYEE", "name": "T"},
    )
    elapsed = time.perf_counter() - t0
    release.set()

    assert res.status_code == 200, res.text
    assert res.json().get("token")
    assert elapsed < 5.0, f"register took {elapsed:.2f}s — Supabase sync is blocking"
    assert invoked.wait(timeout=5.0), "background Supabase sync was never invoked"


def test_supabase_call_timeout_returns_false(monkeypatch):
    """A hung admin call must time out and return False rather than block."""
    from unittest.mock import MagicMock

    import backend.app.services.supabase_auth_sync as sync_mod

    # Force a short timeout so the test runs fast.
    monkeypatch.setattr(sync_mod, "_SUPABASE_CALL_TIMEOUT_S", 0.5)

    client_mock = MagicMock()

    def _block_forever(*_args, **_kwargs):
        time.sleep(30)

    client_mock.auth.admin.create_user.side_effect = _block_forever
    monkeypatch.setattr(sync_mod, "get_supabase_admin_client", lambda: client_mock)

    t0 = time.perf_counter()
    ok = sync_mod.sync_relopass_user_to_supabase_auth(
        "x@y.com",
        "secret123",
        relopass_user_id="user-uuid-1",
    )
    elapsed = time.perf_counter() - t0

    assert ok is False
    assert elapsed < 3.0, f"timeout not enforced (took {elapsed:.2f}s)"
