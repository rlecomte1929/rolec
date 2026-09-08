"""AIQ-1330 — admin Companies per-company KPI tiles must not regress to 0.

The regression: get_admin_company_index ran an orphan-diagnostics query with
TRIM(profiles.company_id) — a uuid column on Postgres -> btrim(uuid) error ->
aborted the shared transaction -> the enrich-count queries failed -> every tile
zeroed. Fix: the diagnostics run on their own connection (and are cast to text),
isolated from the enrich counts.

SQLite has no uuid type, so the prod-specific abort can't be reproduced here; these
tests instead lock the two behavioural guarantees that matter:
  1. enrich counts populate (non-zero) for a seeded company;
  2. a failure in the orphan diagnostics can NEVER zero the tiles.

Root conftest mocks backend.database, so we import the real CompaniesMixin directly
and give it a real engine + minimal _row_to_dict/_rows_to_list.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402

import backend.database as _bd  # the conftest mock module  # noqa: E402
import backend.db.companies as companies_mod  # noqa: E402
from backend.db.companies import CompaniesMixin  # noqa: E402


class _DB(CompaniesMixin):
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _row_to_dict(row):
        return dict(row._mapping) if row is not None else None

    @staticmethod
    def _rows_to_list(rows):
        return [dict(r._mapping) for r in rows]


_SCHEMA = """
CREATE TABLE companies (id TEXT PRIMARY KEY, name TEXT, legal_name TEXT, hr_contact TEXT);
CREATE TABLE hr_users (company_id TEXT, profile_id TEXT, created_at TEXT);
CREATE TABLE employees (company_id TEXT);
CREATE TABLE company_policies (company_id TEXT);
CREATE TABLE relocation_cases (id TEXT, company_id TEXT);
CREATE TABLE case_assignments (id TEXT, case_id TEXT, canonical_case_id TEXT, hr_user_id TEXT);
CREATE TABLE profiles (id TEXT, full_name TEXT, email TEXT);
"""

_SEED = """
INSERT INTO companies (id, name) VALUES ('c1', 'Acme'), ('c2', 'Globex'), ('c3', 'Brand New Co 1782553314571');
INSERT INTO hr_users (company_id, profile_id, created_at) VALUES ('c1', 'p1', '2026-01-01');
INSERT INTO employees (company_id) VALUES ('c1'), ('c1');
INSERT INTO relocation_cases (id, company_id) VALUES ('case1', 'c1');
-- [AIQ-1737·2] Intentional NULL canonical: 'a1' is the orphan fixture the
-- orphan-diagnostics regression tests below depend on. Isolated in-memory schema —
-- AIQ-1732's prod NOT NULL(canonical_case_id) does not govern it.
INSERT INTO case_assignments (id, case_id, canonical_case_id, hr_user_id) VALUES ('a1', 'case1', NULL, 'p1');
INSERT INTO profiles (id, full_name, email) VALUES ('p1', 'Boss', 'boss@acme.test');
"""


class AdminCompanyIndexTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in (_SCHEMA + _SEED).split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.db = _DB(self.engine)
        # join_on_cases must use the SQLite variant; _is_sqlite is computed from
        # DATABASE_URL at import and may be False locally.
        p1 = mock.patch.object(companies_mod, "_is_sqlite", True)
        p1.start(); self.addCleanup(p1.stop)
        # _table_columns is lazily imported from the (mocked) backend.database;
        # return [] so the is_test visibility guard is skipped.
        _bd._table_columns = lambda *a, **k: []
        self.addCleanup(lambda: setattr(_bd, "_table_columns", mock.MagicMock()))

    def _row(self, result, name):
        return next(r for r in result if r["name"] == name)

    def test_per_company_counts_are_nonzero(self):
        result = self.db.get_admin_company_index()
        acme = self._row(result, "Acme")
        self.assertGreaterEqual(acme["hr_users_count"], 1)
        self.assertGreaterEqual(acme["employee_count"], 2)
        self.assertGreaterEqual(acme["assignments_count"], 1)
        # a company with no members stays at 0 (sanity, not a false-positive)
        self.assertEqual(self._row(result, "Globex")["hr_users_count"], 0)

    def test_synthetic_named_companies_hidden(self):
        # [AIQ-1325a-followup] 'Brand New Co <epoch>' is filtered by name even when
        # is_test is unset (the is_test guard is skipped here, mirroring prod's
        # pre-flag rows); real tenants remain.
        result = self.db.get_admin_company_index()
        names = {r["name"] for r in result}
        self.assertNotIn("Brand New Co 1782553314571", names)
        self.assertIn("Acme", names)
        # include_test=True still shows everything
        all_names = {r["name"] for r in self.db.get_admin_company_index(include_test=True)}
        self.assertIn("Brand New Co 1782553314571", all_names)

    def test_orphan_diagnostics_failure_does_not_zero_tiles(self):
        # The regression's behavioural guarantee: even if the orphan diagnostics
        # blow up entirely, the enrich counts must still populate.
        with mock.patch.object(
            _DB, "_log_orphan_company_ids", side_effect=RuntimeError("boom")
        ):
            result = self.db.get_admin_company_index()
        acme = self._row(result, "Acme")
        self.assertGreaterEqual(acme["hr_users_count"], 1)
        self.assertGreaterEqual(acme["employee_count"], 2)
        self.assertGreaterEqual(acme["assignments_count"], 1)


if __name__ == "__main__":
    unittest.main()
