"""AIQ-1360 — require_role and the role gates check roles[] membership.

A multi-role user passes any role they hold; ADMIN passes all; legacy users with
only the single `role` field still work via the fallback.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from backend.app.auth_deps import (  # noqa: E402
    require_role,
    require_hr_or_employee,
    require_admin_or_hr,
    require_admin,
    derive_roles,
)
from backend.schemas import UserRole  # noqa: E402


def test_multirole_user_passes_each_held_role():
    u = {"role": "EMPLOYEE", "roles": ["HR", "EMPLOYEE"], "is_admin": False}
    assert require_role(UserRole.HR)(user=u) is u
    assert require_role(UserRole.EMPLOYEE)(user=u) is u


def test_wrong_role_employee_gate_uses_not_an_employee_code():
    u = {"role": "HR", "roles": ["HR"], "is_admin": False}
    with pytest.raises(HTTPException) as exc:
        require_role(UserRole.EMPLOYEE)(user=u)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "NOT_AN_EMPLOYEE"


def test_single_role_user_denied_unheld_role():
    u = {"role": "EMPLOYEE", "roles": ["EMPLOYEE"], "is_admin": False}
    with pytest.raises(HTTPException) as exc:
        require_role(UserRole.HR)(user=u)
    assert exc.value.status_code == 403


def test_admin_passes_all_roles():
    u = {"role": "ADMIN", "roles": ["ADMIN"], "is_admin": True}
    assert require_role(UserRole.HR)(user=u) is u
    assert require_role(UserRole.EMPLOYEE)(user=u) is u


def test_legacy_user_without_roles_field_falls_back():
    u = {"role": "HR"}  # legacy session, no roles[]
    assert require_role(UserRole.HR)(user=u) is u
    with pytest.raises(HTTPException):
        require_role(UserRole.EMPLOYEE)(user=u)


def test_hr_or_employee_and_admin_or_hr_use_membership():
    multi = {"role": "EMPLOYEE", "roles": ["HR", "EMPLOYEE"], "is_admin": False}
    assert require_hr_or_employee(user=multi) is multi
    assert require_admin_or_hr(user=multi) is multi  # holds HR
    emp_only = {"role": "EMPLOYEE", "roles": ["EMPLOYEE"], "is_admin": False}
    with pytest.raises(HTTPException):
        require_admin_or_hr(user=emp_only)


# ── AIQ-1367 — admin-contract preservation + require_admin hardening ──────────


def test_derive_roles_preserves_admin_contract():
    """[AIQ-1367 #4] An is_admin user always derives ADMIN as a held + primary role,
    even when their only junction row says something else (the #1108 contract that
    #1110's derive_roles regressed). Non-admins are never widened."""
    # Allowlist admin whose sole user_roles row is EMPLOYEE → still derives ADMIN.
    roles, primary = derive_roles([{"role": "EMPLOYEE", "is_primary": True}], "ADMIN", is_admin=True)
    assert "ADMIN" in roles and primary == "ADMIN"
    # Admin with an empty junction → ADMIN from the fallback.
    roles, primary = derive_roles([], "ADMIN", is_admin=True)
    assert roles == ["ADMIN"] and primary == "ADMIN"
    # Non-admin is untouched — ADMIN is never injected from is_admin=False.
    roles, primary = derive_roles([{"role": "EMPLOYEE", "is_primary": True}], "EMPLOYEE", is_admin=False)
    assert roles == ["EMPLOYEE"] and primary == "EMPLOYEE" and "ADMIN" not in roles


def test_require_admin_ignores_a_junction_admin_row_without_is_admin():
    """[AIQ-1367 #5] A rogue user_roles ADMIN row must not grant admin authority.
    Membership require_role(ADMIN) would pass it (the escalation surface) — the
    signed-url endpoint now uses require_admin, which is single-sourced on is_admin."""
    rogue = {"role": "EMPLOYEE", "roles": ["ADMIN", "EMPLOYEE"], "is_admin": False}
    # Membership-based guard WOULD have admitted the rogue row …
    assert require_role(UserRole.ADMIN)(user=rogue) is rogue
    # … but require_admin (is_admin only) denies it.
    with pytest.raises(HTTPException) as exc:
        require_admin(user=rogue)
    assert exc.value.status_code == 403
    # A real admin still passes.
    real = {"role": "ADMIN", "roles": ["ADMIN"], "is_admin": True}
    assert require_admin(user=real) is real
