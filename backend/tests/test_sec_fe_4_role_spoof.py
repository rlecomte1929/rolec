"""
SEC-FE-4 / AIQ-1171 — server-side role authz cannot be bypassed by a spoofed client role.

The frontend stores the caller's role in a client-writable localStorage key
(``relopass_role``). These tests prove that value is irrelevant to access control:
authz is decided from the SERVER-resolved identity (``users.role`` / ``is_admin``),
not from anything the client claims.

Harness: mount the prod app (``backend.main:app``) and override the SERVER identity
dependency to inject a fixed caller. There are two ``get_current_user`` functions in
this codebase (``backend.app.auth_deps`` for modular routers, and a second copy in
``backend.main`` used by the main.py-registered routes); the route that serves a
given path may use either, so BOTH are overridden. A spoofed-admin client that is
really a plain employee is modelled by injecting an employee identity — the route
guards run on the injected (server) identity, so the client's spoof has no effect.

The denial path (403) is reached at the dependency layer, before any handler body or
DB access. Positive controls assert only that a true admin/HR is NOT rejected for
auth reasons (401/403) — the handler may then 500 on the bare test DB, which still
proves the role guard let the privileged caller through.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

import backend.main as bm
from backend.main import app
from backend.app import auth_deps

# A plain employee whose CLIENT has spoofed relopass_role=ADMIN in localStorage.
# The server identity is what the backend actually resolves from the token.
_SPOOFED_EMPLOYEE = {
    "id": "emp-spoof-1",
    "role": "EMPLOYEE",
    "is_admin": False,
    "email": "employee@testcompany.com",
    "company": "co-employee",
}
_TRUE_ADMIN = {
    "id": "admin-1",
    "role": "ADMIN",
    "is_admin": True,
    "email": "ops@relopass.com",
    "company": None,
}
_TRUE_HR = {
    "id": "hr-1",
    "role": "HR",
    "is_admin": False,
    "email": "hr@testcompany.com",
    "company": "co-1",
}


def _client(identity):
    # Override BOTH get_current_user variants — the serving route may use either.
    app.dependency_overrides[auth_deps.get_current_user] = lambda: identity
    app.dependency_overrides[bm.get_current_user] = lambda: identity
    # raise_server_exceptions=False so a handler 500 on the bare test DB becomes a
    # 500 response (the guard already passed) rather than failing the test.
    return TestClient(app, raise_server_exceptions=False)


def _clear():
    app.dependency_overrides.pop(auth_deps.get_current_user, None)
    app.dependency_overrides.pop(bm.get_current_user, None)


_AUTH_REJECT = {401, 403}


# Admin-only route (require_admin) and an HR-only route (require_role(HR)).
ADMIN_ROUTE = "/api/admin/companies"
HR_ROUTE = "/api/hr/backlog"


def test_spoofed_employee_cannot_reach_admin_route():
    """A client claiming ADMIN but with an employee server-identity → 403."""
    client = _client(_SPOOFED_EMPLOYEE)
    try:
        resp = client.get(ADMIN_ROUTE)
    finally:
        _clear()
    assert resp.status_code == 403, (
        f"spoofed employee reached admin route (status={resp.status_code}); "
        "server-side require_admin failed to deny"
    )


def test_spoofed_employee_cannot_reach_hr_route():
    """Employee server-identity → HR-only route → 403, regardless of client role."""
    client = _client(_SPOOFED_EMPLOYEE)
    try:
        resp = client.get(HR_ROUTE)
    finally:
        _clear()
    assert resp.status_code == 403, (
        f"employee reached HR-only route (status={resp.status_code})"
    )


def test_true_admin_passes_admin_guard():
    """Positive control: a real admin is NOT blocked by the guard (no blanket deny)."""
    client = _client(_TRUE_ADMIN)
    try:
        resp = client.get(ADMIN_ROUTE)
    finally:
        _clear()
    assert resp.status_code not in _AUTH_REJECT, (
        f"true admin was denied by admin guard (status={resp.status_code})"
    )


def test_true_hr_passes_hr_guard():
    """Positive control: a real HR user is NOT blocked by the HR guard."""
    client = _client(_TRUE_HR)
    try:
        resp = client.get(HR_ROUTE)
    finally:
        _clear()
    assert resp.status_code not in _AUTH_REJECT, (
        f"true HR was denied by HR guard (status={resp.status_code})"
    )
