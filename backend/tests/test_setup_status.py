"""GET /api/hr/setup-status — read-only HR workspace setup progress.

Mounted on the prod app (``backend.main:app``) so the suite also proves the
dual-registration hard gate. Auth deps are overridden; the four field-derivation
helpers are monkeypatched with a per-company data map so the tests exercise the
route wiring, the next_step ordering, and — critically — that the company scope
comes ONLY from auth (``get_org_id_for_hr_user``), never from a param/body, so
one HR user can never see another company's status.

``cases_count`` / ``first_case_id`` are derived from ``public.relocation_cases``
(live HR-created cases, not the seed-data-only ``public.cases`` table). The
``_cases`` helper is monkeypatched here; the real table is verified by the fact
that the helper queries ``relocation_cases`` (see setup_assistant.py).
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import setup_assistant

# Per-company synthetic workspace state, keyed by company_id.
# ``cases`` values represent rows in ``public.relocation_cases`` (live HR-created
# cases), NOT ``public.cases`` (seed-data only — see setup_assistant._cases).
_DATA = {
    # Fresh self-serve signup: no profile, no policy, no relocation_cases rows, no employees.
    "co-fresh": {"profile": False, "policy": False, "cases": (0, None), "employees": 0},
    # Advanced: profile + policy done, one relocation_cases row, no employee invited yet.
    "co-advanced": {"profile": True, "policy": True, "cases": (1, "case-abc"), "employees": 0},
    # A DIFFERENT company whose relocation_cases rows must never leak to another caller.
    "co-other": {"profile": True, "policy": True, "cases": (7, "case-other"), "employees": 4},
}

_HR = {"id": "hr-1", "role": "HR", "company": None, "is_admin": False, "auth_uuid": None}


@pytest.fixture(autouse=True)
def _patch_helpers(monkeypatch):
    """Route the four helpers through the per-company map so each derived field
    is a pure function of the company_id the endpoint resolved from auth."""
    monkeypatch.setattr(setup_assistant, "_company_profile_complete",
                        lambda cid: _DATA.get(cid, {}).get("profile", False))
    monkeypatch.setattr(setup_assistant, "_policy_published",
                        lambda cid: _DATA.get(cid, {}).get("policy", False))
    monkeypatch.setattr(setup_assistant, "_cases",
                        lambda cid: _DATA.get(cid, {}).get("cases", (0, None)))
    monkeypatch.setattr(setup_assistant, "_employees_invited",
                        lambda cid: _DATA.get(cid, {}).get("employees", 0))
    yield


def _client_for(company_id: str) -> TestClient:
    """A TestClient whose auth resolves to ``company_id`` (scope from auth only)."""
    app.dependency_overrides[auth_deps.require_admin_or_hr] = lambda: _HR
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: company_id
    return TestClient(app)


def _clear_overrides():
    app.dependency_overrides.pop(auth_deps.require_admin_or_hr, None)
    app.dependency_overrides.pop(auth_deps.get_org_id_for_hr_user, None)


def test_route_registered_in_prod_app():
    assert "/api/hr/setup-status" in {r.path for r in app.routes}


def test_fresh_company_next_step_is_company_profile():
    try:
        r = _client_for("co-fresh").get("/api/hr/setup-status")
        assert r.status_code == 200
        body = r.json()
        assert body["company_profile_complete"] is False
        assert body["policy_published"] is False
        assert body["cases_count"] == 0
        assert body["employees_invited"] == 0
        assert body["first_case_id"] is None
        assert body["next_step"] == {
            "label": "Complete your company profile",
            "route": "/hr/company-profile",
        }
    finally:
        _clear_overrides()


def test_advanced_company_counts_and_next_step():
    try:
        r = _client_for("co-advanced").get("/api/hr/setup-status")
        assert r.status_code == 200
        body = r.json()
        assert body["company_profile_complete"] is True
        assert body["policy_published"] is True
        assert body["cases_count"] == 1
        assert body["first_case_id"] == "case-abc"
        assert body["employees_invited"] == 0
        # Profile + policy + a case done → the first incomplete stage is invite.
        assert body["next_step"]["label"] == "Invite your first employee"
        assert body["next_step"]["route"] == "/hr/command-center"
    finally:
        _clear_overrides()


def test_company_scoping_no_cross_company_leak():
    """Each caller sees ONLY their own company's status; co-other's data
    (7 cases, 4 employees) never appears for the co-advanced caller, and a
    ``?company_id=`` query param cannot override the auth-derived scope."""
    try:
        advanced = _client_for("co-advanced").get(
            "/api/hr/setup-status?company_id=co-other"
        )
        assert advanced.status_code == 200
        b1 = advanced.json()
        # Param-injection ignored: still co-advanced's numbers, not co-other's.
        assert b1["cases_count"] == 1 and b1["first_case_id"] == "case-abc"
        assert b1["employees_invited"] == 0
    finally:
        _clear_overrides()

    try:
        other = _client_for("co-other").get("/api/hr/setup-status")
        assert other.status_code == 200
        b2 = other.json()
        assert b2["cases_count"] == 7 and b2["first_case_id"] == "case-other"
        assert b2["employees_invited"] == 4
        # All done → the "set up" terminal step.
        assert b2["next_step"]["label"] == "You're all set up"
    finally:
        _clear_overrides()


def test_unauthenticated_is_rejected():
    _clear_overrides()  # no auth override → real require_admin_or_hr runs
    r = TestClient(app).get("/api/hr/setup-status")
    assert r.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Integration tests for _employees_invited — real SQLite engine, real SQL
# --------------------------------------------------------------------------- #
import unittest
from unittest import mock

from sqlalchemy import create_engine, text as _text

from backend.app.routers import setup_assistant as _sa

# Capture the real function BEFORE _patch_helpers autouse replaces it.
# Each test restores it in setUp so the SQL actually executes.
_REAL_EMPLOYEES_INVITED = _sa._employees_invited

# Minimal schema — only the columns _employees_invited actually touches.
_SCHEMA = """
CREATE TABLE relocation_cases (
    id   TEXT PRIMARY KEY,
    company_id TEXT NOT NULL
);
CREATE TABLE case_assignments (
    id                  TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL,
    employee_user_id    TEXT,
    employee_identifier TEXT
);
"""


def _make_engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with eng.begin() as conn:
        for stmt in _SCHEMA.split(";"):
            if stmt.strip():
                conn.execute(_text(stmt))
    return eng


class TestEmployeesInvitedHelper(unittest.TestCase):
    """Direct unit tests on _employees_invited using a SQLite in-memory engine.

    These tests bypass the route layer so they exercise the actual SQL and
    prove the fix for the under-counting bug (NULL employees.company_id).
    """

    def setUp(self):
        self.engine = _make_engine()
        # The autouse _patch_helpers fixture replaces _sa._employees_invited with
        # a lambda keyed on _DATA.  Restore the real SQL function before each test
        # so our assertions actually exercise the query.
        _sa._employees_invited = _REAL_EMPLOYEES_INVITED
        self._patcher = mock.patch.object(_sa.db, "engine", self.engine)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        # Put the lambda back so later pytest-style tests get the autouse fixture.
        # (monkeypatch will overwrite this again anyway on the next test setup.)
        _sa._employees_invited = lambda cid: _DATA.get(cid, {}).get("employees", 0)

    def _seed(self, conn, *, case_id, company_id, assign_id, employee_user_id=None, employee_identifier=None):
        conn.execute(
            _text("INSERT OR IGNORE INTO relocation_cases (id, company_id) VALUES (:cid, :co)"),
            {"cid": case_id, "co": company_id},
        )
        conn.execute(
            _text(
                "INSERT INTO case_assignments (id, case_id, employee_user_id, employee_identifier)"
                " VALUES (:aid, :cid, :euid, :eid)"
            ),
            {"aid": assign_id, "cid": case_id, "euid": employee_user_id, "eid": employee_identifier},
        )

    # (a) A company with one assignment counts ≥ 1 and next_step advances past "invite employee".
    def test_assignment_counts_for_company(self):
        with self.engine.begin() as conn:
            self._seed(conn, case_id="case-1", company_id="co-A",
                       assign_id="a1", employee_user_id="emp-uuid-1")
        result = _sa._employees_invited("co-A")
        self.assertGreaterEqual(result, 1)
        # next_step must have advanced past "Invite your first employee"
        ns = _sa._next_step(
            profile_complete=True, policy_published=True,
            cases_count=1, employees_invited=result,
        )
        self.assertNotEqual(ns.label, "Invite your first employee")
        self.assertEqual(ns.label, "You're all set up")

    # (b) Scoping — a second company's assignments/cases do NOT bleed into co-A.
    def test_scoping_second_company_does_not_count(self):
        with self.engine.begin() as conn:
            self._seed(conn, case_id="case-1", company_id="co-A",
                       assign_id="a1", employee_user_id="emp-uuid-1")
            # co-B has 5 employees assigned across 2 cases.
            self._seed(conn, case_id="case-B1", company_id="co-B",
                       assign_id="b1", employee_user_id="emp-b1")
            self._seed(conn, case_id="case-B2", company_id="co-B",
                       assign_id="b2", employee_user_id="emp-b2")
        self.assertEqual(_sa._employees_invited("co-A"), 1)
        self.assertEqual(_sa._employees_invited("co-B"), 2)

    # (c) Regression fix: NULL employees.company_id is still counted.
    # Seed a relocation_cases row for co-A + a case_assignments row referencing it,
    # with NO matching employees row (i.e. employee has NULL employees.company_id
    # or simply doesn't exist in the employees table). Must still return ≥ 1.
    def test_null_employee_company_id_still_counted(self):
        with self.engine.begin() as conn:
            self._seed(
                conn,
                case_id="case-null-co", company_id="co-A",
                assign_id="a-null",
                # employee_user_id is set but there is no row in employees table
                # with company_id='co-A' — this is the exact prod regression scenario.
                employee_user_id="emp-no-company-in-employees-table",
            )
        result = _sa._employees_invited("co-A")
        self.assertGreaterEqual(result, 1,
            "Employee with no employees.company_id row must still be counted via case_assignments")
