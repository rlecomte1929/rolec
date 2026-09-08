"""Admin people index link counts must match the old correlated COUNT(*) SQL.

GET /api/admin/people is one query in UsersMixin.get_admin_people_index.
The rewrite LEFT JOINs pre-aggregated hr_users / employees counts; this file
keeps the previous SELECT expressions as the oracle so counts cannot drift.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402

import backend.database as _bd  # the conftest mock module  # noqa: E402
import backend.db.users as users_mod  # noqa: E402
from backend.db.users import UsersMixin  # noqa: E402


class _DB(UsersMixin):
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _row_to_dict(row):
        return dict(row._mapping) if row is not None else None

    @staticmethod
    def _rows_to_list(rows):
        return [dict(r._mapping) for r in rows]


# Oracle: the correlated subqueries this rewrite replaced. Do not "improve" this
# string to match production — the test exists to prove the join rewrite agrees.
_ORACLE_COUNTS_SQL = """
    SELECT p.id,
           (SELECT COUNT(*) FROM hr_users hu WHERE hu.profile_id = CAST(p.id AS TEXT)) AS hr_link_count,
           (SELECT COUNT(*) FROM employees e WHERE e.profile_id = CAST(p.id AS TEXT)) AS employee_link_count
    FROM profiles p
"""

_SCHEMA = """
CREATE TABLE companies (id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE profiles (
    id TEXT PRIMARY KEY,
    role TEXT,
    email TEXT,
    full_name TEXT,
    company_id TEXT
);
CREATE TABLE hr_users (id TEXT PRIMARY KEY, company_id TEXT, profile_id TEXT);
CREATE TABLE employees (id TEXT PRIMARY KEY, company_id TEXT, profile_id TEXT);
"""

_SEED = """
INSERT INTO companies (id, name) VALUES ('c1', 'Acme');
INSERT INTO profiles (id, role, email, full_name, company_id) VALUES
    ('p-linked', 'EMPLOYEE', 'linked@acme.test', 'Linked Person', 'c1'),
    ('p-plain', 'EMPLOYEE', 'plain@acme.test', 'Plain Person', 'c1');
INSERT INTO hr_users (id, company_id, profile_id) VALUES
    ('hu-1', 'c1', 'p-linked');
INSERT INTO employees (id, company_id, profile_id) VALUES
    ('e-1', 'c1', 'p-linked'),
    ('e-2', 'c1', 'p-linked');
"""


class AdminPeopleIndexLinkCountTests(unittest.TestCase):
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
        p1 = mock.patch.object(users_mod, "_is_sqlite", True)
        p1.start()
        self.addCleanup(p1.stop)
        _bd._table_columns = lambda *a, **k: []
        self.addCleanup(lambda: setattr(_bd, "_table_columns", mock.MagicMock()))

    def test_link_counts_match_correlated_subquery_oracle(self):
        people, summary = self.db.get_admin_people_index()
        with self.engine.connect() as conn:
            oracle_rows = conn.execute(text(_ORACLE_COUNTS_SQL)).fetchall()
        oracle = {str(r._mapping["id"]): r._mapping for r in oracle_rows}

        by_id = {str(p["id"]): p for p in people}
        self.assertEqual(set(by_id), set(oracle))
        self.assertEqual(by_id["p-linked"]["hr_link_count"], 1)
        self.assertEqual(by_id["p-linked"]["employee_link_count"], 2)
        self.assertEqual(by_id["p-plain"]["hr_link_count"], 0)
        self.assertEqual(by_id["p-plain"]["employee_link_count"], 0)
        for pid, row in by_id.items():
            self.assertEqual(int(row["hr_link_count"]), int(oracle[pid]["hr_link_count"]))
            self.assertEqual(int(row["employee_link_count"]), int(oracle[pid]["employee_link_count"]))

        linked = by_id["p-linked"]
        self.assertEqual(linked["name"], "Linked Person")
        self.assertEqual(linked["status"], "active")
        self.assertEqual(linked["company_name"], "Acme")
        self.assertEqual(summary["count"], 2)
        self.assertIn("orphans_without_company", summary)


if __name__ == "__main__":
    unittest.main()
