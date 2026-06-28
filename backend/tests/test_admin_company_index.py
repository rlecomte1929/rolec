"""AIQ-1330 — Admin Companies per-company KPI tiles.

Coverage gap: `get_admin_company_index` (the per-company HR/employee/case rollup
behind /admin/companies) had NO tests, so a regression could ship silently. Two
guards here:

1. happy path — a company with 1 HR user + 1 employee + 1 case shows non-zero tiles.
2. resilience (the real AIQ-1330 fix) — if ONE aggregate query fails, the other tiles
   must NOT be zeroed. Previously a single broad try/except blanked every tile for
   every company on any error.

Exercises the REAL CompaniesMixin against in-memory SQLite on an isolated host (no
global db singleton). NOTE: SQLite is all-text so it can't reproduce the Postgres
uuid/text skew — these tests lock behaviour + resilience, not the type cast itself.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.db.companies import CompaniesMixin  # noqa: E402


class _Host(CompaniesMixin):
    def __init__(self, engine) -> None:
        self.engine = engine


def _make_engine(with_cases: bool = True):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as c:
        c.execute(text("CREATE TABLE companies (id TEXT, name TEXT, hr_contact TEXT)"))
        c.execute(text("CREATE TABLE hr_users (id TEXT, company_id TEXT, profile_id TEXT, created_at TEXT)"))
        c.execute(text("CREATE TABLE employees (id TEXT, company_id TEXT)"))
        c.execute(text("CREATE TABLE case_assignments (id TEXT, case_id TEXT, canonical_case_id TEXT, hr_user_id TEXT)"))
        c.execute(text("CREATE TABLE profiles (id TEXT, full_name TEXT, email TEXT, company_id TEXT)"))
        c.execute(text("CREATE TABLE company_policies (company_id TEXT)"))
        if with_cases:
            c.execute(text("CREATE TABLE relocation_cases (id TEXT, company_id TEXT)"))
            c.execute(text("INSERT INTO relocation_cases (id, company_id) VALUES ('case-1', 'comp-1')"))

        c.execute(text("INSERT INTO companies (id, name, hr_contact) VALUES ('comp-1', 'Acme', NULL)"))
        c.execute(text("INSERT INTO hr_users (id, company_id, profile_id, created_at) VALUES ('hru-1', 'comp-1', 'prof-1', '2026-01-01')"))
        c.execute(text("INSERT INTO employees (id, company_id) VALUES ('emp-1', 'comp-1')"))
        c.execute(text("INSERT INTO case_assignments (id, case_id, canonical_case_id, hr_user_id) VALUES ('asgn-1', 'case-1', NULL, 'prof-1')"))
        c.execute(text("INSERT INTO profiles (id, full_name, email, company_id) VALUES ('prof-1', 'HR One', 'hr@acme.test', NULL)"))
    return engine


def _acme(rows):
    return next(r for r in rows if r["id"] == "comp-1")


def test_kpi_tiles_nonzero_happy_path():
    rows = _Host(_make_engine()).get_admin_company_index(include_test=True)
    acme = _acme(rows)
    assert acme["hr_users_count"] >= 1, acme
    assert acme["employee_count"] >= 1, acme
    assert acme["assignments_count"] >= 1, acme
    assert acme["primary_contact_name"] == "HR One"


def test_one_failing_aggregate_does_not_zero_the_others():
    # relocation_cases is absent → the assignments rollup query errors. The other
    # tiles must still populate (regression guard for the per-aggregate isolation).
    rows = _Host(_make_engine(with_cases=False)).get_admin_company_index(include_test=True)
    acme = _acme(rows)
    assert acme["hr_users_count"] >= 1, "HR tile zeroed by an unrelated aggregate failure"
    assert acme["employee_count"] >= 1, "Employee tile zeroed by an unrelated aggregate failure"
    assert acme["assignments_count"] == 0  # the only tile that should degrade
