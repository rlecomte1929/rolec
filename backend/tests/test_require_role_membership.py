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
)
from backend.schemas import UserRole  # noqa: E402


def test_multirole_user_passes_each_held_role():
    u = {"role": "EMPLOYEE", "roles": ["HR", "EMPLOYEE"], "is_admin": False}
    assert require_role(UserRole.HR)(user=u) is u
    assert require_role(UserRole.EMPLOYEE)(user=u) is u


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
