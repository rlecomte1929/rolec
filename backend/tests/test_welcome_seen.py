"""AIQ-1701 — POST /api/auth/welcome-seen + the welcome_seen flag on the login response.

The first-login welcome dismissal used to live only in the browser's localStorage, so a
returning user on a new device was re-onboarded. It is now owned by
`profiles.welcome_seen_at` and mirrored to the client at login, which keeps the
client-side redirect check synchronous.

Handlers are exercised directly with db helpers monkeypatched (same approach as
test_switch_role.py) — the UPDATE itself is validated against real Postgres, since
sqlite has no now().
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.routers import auth as authmod  # noqa: E402


def test_marks_welcome_seen_for_the_calling_user(monkeypatch):
    seen = []
    monkeypatch.setattr(authmod.db, "mark_welcome_seen", lambda uid: seen.append(uid) or True)

    out = authmod.mark_welcome_seen(user={"id": "u1", "role": "HR"})

    assert seen == ["u1"], "the id must come from the token, never from a request body"
    assert out == {"welcome_seen": True, "persisted": True}


def test_id_comes_from_the_token_so_one_user_cannot_dismiss_anothers(monkeypatch):
    # The endpoint takes no body at all — there is no field an attacker could set.
    import inspect

    params = inspect.signature(authmod.mark_welcome_seen).parameters
    assert list(params) == ["user"], "endpoint must accept no request body"


def test_unpersistable_user_degrades_instead_of_failing(monkeypatch):
    # Legacy non-UUID seed id → no profiles row → False. The client has already written
    # its localStorage flag, so this must not error: the dismissal just stays local,
    # which is the pre-AIQ-1701 behaviour.
    monkeypatch.setattr(authmod.db, "mark_welcome_seen", lambda uid: False)

    out = authmod.mark_welcome_seen(user={"id": "legacy-seed-1", "role": "HR"})

    assert out == {"welcome_seen": True, "persisted": False}


def test_db_helper_returns_false_for_a_non_uuid_id():
    # Guards the early return before any SQL runs (mirrors get_profile_record).
    # conftest mocks backend.database, so exercise the real mixin method directly —
    # the id check happens before self.engine is ever touched, so a bare object works.
    from backend.db.users import UsersMixin

    assert UsersMixin.mark_welcome_seen(object(), "not-a-uuid") is False
    assert UsersMixin.mark_welcome_seen(object(), "") is False
    assert UsersMixin.mark_welcome_seen(object(), None) is False


def test_route_registered_on_prod_app():
    # Dual-layer trap: the route lives on the existing auth router, which is already
    # mounted in BOTH app instances — this asserts the one that actually serves prod.
    from backend.main import app

    assert any("/api/auth/welcome-seen" == r.path for r in app.routes)


def test_user_response_carries_welcome_seen_and_defaults_false():
    from backend.schemas import UserResponse, UserRole

    assert UserResponse(id="u1", role=UserRole.HR).welcome_seen is False
    assert UserResponse(id="u1", role=UserRole.HR, welcome_seen=True).welcome_seen is True
