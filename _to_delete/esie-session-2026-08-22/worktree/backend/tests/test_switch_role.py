"""AIQ-1355 — POST /api/auth/switch-role.

Switch to a held role → 200 + is_primary persisted; unheld role → 403. The route
handler is exercised directly (db helpers monkeypatched) to avoid a live DB; a
separate check asserts the route is registered on the prod app instance.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from backend.app.routers import auth as authmod  # noqa: E402


def test_switch_to_held_role_sets_primary_and_returns_roles(monkeypatch):
    calls = []
    monkeypatch.setattr(authmod.db, "set_primary_role", lambda uid, role: calls.append((uid, role)))
    monkeypatch.setattr(
        authmod.db, "get_user_roles",
        lambda uid: [{"role": "HR", "is_primary": True}, {"role": "EMPLOYEE", "is_primary": False}],
    )
    user = {"id": "u1", "role": "EMPLOYEE", "roles": ["HR", "EMPLOYEE"]}
    out = authmod.switch_role(body={"role": "HR"}, user=user)
    assert calls == [("u1", "HR")]
    assert out["primary_role"] == "HR"
    assert set(out["roles"]) == {"HR", "EMPLOYEE"}


def test_switch_to_unheld_role_is_forbidden():
    user = {"id": "u1", "role": "EMPLOYEE", "roles": ["EMPLOYEE"]}
    with pytest.raises(HTTPException) as exc:
        authmod.switch_role(body={"role": "ADMIN"}, user=user)
    assert exc.value.status_code == 403


def test_switch_role_route_registered_on_prod_app():
    from backend.main import app  # imported lazily; QUERY_COUNTER_OFF set above
    assert any("/api/auth/switch-role" == r.path for r in app.routes)
