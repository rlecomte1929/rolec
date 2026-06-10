"""
W0-2: keep auth identity resolution converged across the dual-layer backend.

Two issues this guards:

1. The monolith `backend.main.get_current_user` historically returned the user
   WITHOUT setting `is_admin`, so `require_admin` / `require_role` there would
   silently 403 admins resolved via the allowlist or profiles.role (rather than
   a role claim). It must now mirror `app/auth_deps.get_current_user`.

2. New routers live under `backend/app/routers/` and must depend on the
   canonical `app/auth_deps.get_current_user`, never on the monolith copy —
   otherwise test `dependency_overrides` keyed to the wrong reference never fire
   (the documented CLAUDE.md footgun).
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import types

import pytest

import backend.main as M
from backend.schemas import UserRole


# --- 1. Monolith get_current_user resolves admin identity ------------------

def _fake_request():
    return types.SimpleNamespace(state=types.SimpleNamespace())


def _run(coro):
    return asyncio.run(coro)


def test_main_get_current_user_sets_is_admin_via_allowlist(monkeypatch):
    """Employee-role token + @relopass.com + allowlisted → is_admin True, role ADMIN."""
    monkeypatch.setattr(
        M.db, "get_user_context_by_token",
        lambda token: {"id": "u1", "email": "admin@relopass.com", "role": "employee"},
    )
    monkeypatch.setattr(M.db, "ensure_profile_record", lambda **kw: None)
    monkeypatch.setattr(M.db, "get_profile_record", lambda uid: None)
    monkeypatch.setattr(M.db, "is_admin_allowlisted", lambda email: True)

    user = _run(M.get_current_user(_fake_request(), "Bearer tok"))
    assert user["is_admin"] is True
    assert user["role"] == UserRole.ADMIN.value


def test_main_get_current_user_non_admin_is_false(monkeypatch):
    """Plain employee (non-relopass email) → is_admin False."""
    monkeypatch.setattr(
        M.db, "get_user_context_by_token",
        lambda token: {"id": "u2", "email": "bob@acme.com", "role": "employee"},
    )
    monkeypatch.setattr(M.db, "ensure_profile_record", lambda **kw: None)
    monkeypatch.setattr(M.db, "get_profile_record", lambda uid: None)
    monkeypatch.setattr(M.db, "is_admin_allowlisted", lambda email: False)

    user = _run(M.get_current_user(_fake_request(), "Bearer tok"))
    assert user["is_admin"] is False


# --- 2. New routers must not import get_current_user from the monolith ------

_ROUTERS_DIR = pathlib.Path(M.__file__).resolve().parent / "app" / "routers"

# Modules predating this guard that still legitimately import from the monolith.
# Keep this empty for new work; do NOT add to it without migrating to auth_deps.
_GRANDFATHERED: set[str] = set()

_BAD_IMPORT = re.compile(
    r"from\s+(?:\.{2,}main|backend\.main)\s+import\s+[^\n]*\bget_current_user\b"
)


def test_app_routers_use_canonical_get_current_user():
    offenders = []
    for path in _ROUTERS_DIR.glob("*.py"):
        if path.name in _GRANDFATHERED:
            continue
        if _BAD_IMPORT.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert not offenders, (
        "app/routers must import get_current_user from backend.app.auth_deps, "
        f"not the monolith backend.main: {offenders}"
    )
