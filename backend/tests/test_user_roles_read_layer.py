"""AIQ-1353 — multi-role read layer: db.get_user_roles + derive_roles.

In-memory SQLite + the real UsersMixin (pattern: test_submit_intake_step_db.py).
SQLite can't reproduce the Postgres uuid/text skew, so these lock the read +
fallback behaviour, not the cast.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.db.users import UsersMixin  # noqa: E402
from backend.app.auth_deps import derive_roles  # noqa: E402


class _Host(UsersMixin):
    def __init__(self, engine) -> None:
        self.engine = engine


def _engine(with_table: bool = True):
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    if with_table:
        with e.begin() as c:
            c.execute(text("CREATE TABLE user_roles (id TEXT, user_id TEXT, role TEXT, is_primary INTEGER)"))
            c.execute(text(
                "INSERT INTO user_roles (user_id, role, is_primary) "
                "VALUES ('u1','HR',0), ('u1','EMPLOYEE',1)"
            ))
    return e


def test_get_user_roles_returns_all_held_rows():
    rows = _Host(_engine()).get_user_roles("u1")
    assert {r["role"] for r in rows} == {"HR", "EMPLOYEE"}


def test_get_user_roles_is_table_missing_safe():
    assert _Host(_engine(with_table=False)).get_user_roles("u1") == []


def test_derive_roles_two_roles_uses_is_primary():
    rows = _Host(_engine()).get_user_roles("u1")
    roles, primary = derive_roles(rows, "EMPLOYEE")
    assert set(roles) == {"HR", "EMPLOYEE"}
    assert primary == "EMPLOYEE"  # the is_primary row


def test_derive_roles_legacy_fallback_to_single_role():
    assert derive_roles([], "HR") == (["HR"], "HR")
