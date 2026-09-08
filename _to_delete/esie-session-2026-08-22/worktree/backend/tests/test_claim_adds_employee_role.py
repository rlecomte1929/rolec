"""AIQ-1362 — claim/link adds an EMPLOYEE role to an existing account.

When an employee contact is linked to an auth user that already exists (e.g. an HR
user being relocated), link_employee_contact_to_auth_user upserts an EMPLOYEE row
into public.user_roles instead of letting the duplicate-email wall block the person.
Idempotent; the existing primary role is untouched.

Exercises the REAL AuthMixin.link_employee_contact_to_auth_user against in-memory
SQLite on a composed host (get_employee_contact_by_id stubbed so the company-directory
branch — irrelevant here — is skipped).
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.db.auth import AuthMixin  # noqa: E402
from backend.db.misc import MiscMixin  # noqa: E402
from backend.db.users import UsersMixin  # noqa: E402


class _Host(AuthMixin, MiscMixin, UsersMixin):
    def __init__(self, engine) -> None:
        self.engine = engine
        self._initialized = True  # skip init_db inside _exec
        self._init_lock = threading.Lock()

    def get_employee_contact_by_id(self, employee_contact_id, request_id=None):
        # No company_id -> the company-directory assignment branch is skipped.
        return {"id": employee_contact_id, "company_id": None}


def _engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with e.begin() as c:
        c.execute(text("CREATE TABLE employee_contacts (id TEXT, linked_auth_user_id TEXT, updated_at TEXT)"))
        c.execute(text("INSERT INTO employee_contacts (id, linked_auth_user_id) VALUES ('ec1', NULL)"))
        c.execute(text(
            "CREATE TABLE user_roles (id INTEGER PRIMARY KEY, user_id TEXT, role TEXT, "
            "is_primary INTEGER, UNIQUE(user_id, role))"
        ))
        # Existing account already holds HR (primary).
        c.execute(text("INSERT INTO user_roles (user_id, role, is_primary) VALUES ('u1','HR',1)"))
    return e


def test_link_adds_employee_role_without_clobbering_primary():
    host = _Host(_engine())
    host.link_employee_contact_to_auth_user("ec1", "u1")
    roles = {r["role"]: r["is_primary"] for r in host.get_user_roles("u1")}
    assert "EMPLOYEE" in roles and "HR" in roles
    assert roles["HR"] is True       # existing primary untouched
    assert roles["EMPLOYEE"] is False  # added, but not primary


def test_link_employee_role_is_idempotent():
    host = _Host(_engine())
    host.link_employee_contact_to_auth_user("ec1", "u1")
    host.link_employee_contact_to_auth_user("ec1", "u1")
    emp = [r for r in host.get_user_roles("u1") if r["role"] == "EMPLOYEE"]
    assert len(emp) == 1
