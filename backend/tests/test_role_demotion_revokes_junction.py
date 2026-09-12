"""RE-10 — demoting a user must revoke the junction row that keeps their old access.

backend/main.py require_role admits on user_roles membership (AIQ-2285). public.user_roles
was append-only, so demoting an HR user to EMPLOYEE left their HR row in place and they
kept all 89 HR-gated routes over their former company.

Scope note, deliberate: this only revokes an outgoing HR/ADMIN persona. An EMPLOYEE row is
never deleted, because EMPLOYEE is also granted independently by relocation linkage
(AIQ-1362 link_employee_contact_to_auth_user) and the schema has no provenance column to
tell the two apart — removing it would strip a relocating employee with a live case.
The general fix needs that column; see the provenance card.

Real UsersMixin.sync_login_role against in-memory SQLite.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.db.users import UsersMixin  # noqa: E402


class _Host(UsersMixin):
    def __init__(self, engine) -> None:
        self.engine = engine
        self._initialized = True
        self._init_lock = threading.Lock()


def _engine(user_role: str, junction_roles: list[str]):
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with e.begin() as c:
        c.execute(text("CREATE TABLE users (id TEXT, email TEXT, role TEXT)"))
        c.execute(text("INSERT INTO users (id, email, role) VALUES ('u1','p@x.test',:r)"), {"r": user_role})
        c.execute(text(
            "CREATE TABLE user_roles (id INTEGER PRIMARY KEY, user_id TEXT, role TEXT, is_primary BOOLEAN)"
        ))
        for r in junction_roles:
            c.execute(
                text("INSERT INTO user_roles (user_id, role, is_primary) VALUES ('u1',:r,:p)"),
                {"r": r, "p": r == user_role},
            )
    return e


def _roles(engine) -> set[str]:
    with engine.begin() as c:
        return {row[0] for row in c.execute(text("SELECT role FROM user_roles WHERE user_id='u1'"))}


def _login_role(engine) -> str:
    with engine.begin() as c:
        return c.execute(text("SELECT role FROM users WHERE id='u1'")).scalar_one()


def test_demoting_hr_revokes_the_hr_junction_row():
    """The RE-10 case. Fails before the fix: HR survives and require_role(HR) still admits."""
    e = _engine("HR", ["HR", "EMPLOYEE"])
    _Host(e).sync_login_role("EMPLOYEE", user_id="u1")
    assert _login_role(e) == "EMPLOYEE"
    assert "HR" not in _roles(e), "demotion left the HR junction row — 89 HR routes stay open"
    assert "EMPLOYEE" in _roles(e), "must keep the role being moved to"


def test_promoting_an_employee_keeps_their_employee_row():
    """Guard against over-revoking: a relocating employee promoted to HR keeps EMPLOYEE.

    EMPLOYEE is granted independently by relocation linkage, so deleting it here would
    strip a live case. This is why the deletion is restricted to HR/ADMIN.
    """
    e = _engine("EMPLOYEE", ["EMPLOYEE"])
    _Host(e).sync_login_role("HR", user_id="u1")
    assert _login_role(e) == "HR"
    assert "EMPLOYEE" in _roles(e), "promotion stripped the employee's own role"


def test_demoting_admin_revokes_the_admin_junction_row():
    e = _engine("ADMIN", ["ADMIN", "EMPLOYEE"])
    _Host(e).sync_login_role("EMPLOYEE", user_id="u1")
    assert "ADMIN" not in _roles(e)
    assert "EMPLOYEE" in _roles(e)


def test_unchanged_role_is_a_no_op():
    e = _engine("HR", ["HR", "EMPLOYEE"])
    _Host(e).sync_login_role("HR", user_id="u1")
    assert _roles(e) == {"HR", "EMPLOYEE"}


def test_resolving_by_email_also_revokes():
    """set_profile_role passes email as well as id; the revoke must follow either key."""
    e = _engine("HR", ["HR", "EMPLOYEE"])
    _Host(e).sync_login_role("EMPLOYEE", email="P@X.test")
    assert "HR" not in _roles(e)
    assert "EMPLOYEE" in _roles(e)
