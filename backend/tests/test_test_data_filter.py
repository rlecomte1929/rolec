"""AIQ-913 — admin read-surface filter for synthetic e2e/verify seed records.

Validates the SQL fragments in backend/db/test_data_filter.py against a real
SQLite engine: real rows survive, the seeder patterns are excluded, and NULL/
empty values are treated as real (kept).
"""
from __future__ import annotations

import os
import sqlite3
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db.test_data_filter import exclude_test_companies, exclude_test_people  # noqa: E402


class TestDataFilterTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(
            """
            CREATE TABLE companies (name TEXT);
            INSERT INTO companies (name) VALUES
              ('Acme GmbH'), ('Globex'), ('Testing April'),
              ('Other Corp'), ('Test Co (Seed)'), ('Test company'),
              ('Other Corp (Seed)'), ('Probe ISO-A'), ('Probe ISO-B'), (NULL);
            CREATE TABLE people (email TEXT);
            INSERT INTO people (email) VALUES
              ('real.person@acme.com'), ('hr@testcompany.com'),
              ('emp_run_123@testco.com'), ('hr_run_9@testco.com'),
              ('emp_uxfix_1@testco.com'), ('emp_f17_20260613@testco.com'),
              (NULL), ('');
            """
        )

    def tearDown(self):
        self.con.close()

    def test_companies_filter_excludes_only_seeds(self):
        rows = self.con.execute(
            f"SELECT name FROM companies WHERE {exclude_test_companies('name')}"
        ).fetchall()
        names = {r[0] for r in rows}
        # real + NULL kept — incl. 'Testing April' (the real demo, must NOT be caught by a naive Test%)
        self.assertEqual(names, {"Acme GmbH", "Globex", "Testing April", None})
        # every synthetic name gone
        for bad in ("Other Corp", "Test Co (Seed)", "Test company",
                    "Other Corp (Seed)", "Probe ISO-A", "Probe ISO-B"):
            self.assertNotIn(bad, names)

    def test_people_filter_excludes_only_testco_domain(self):
        rows = self.con.execute(
            f"SELECT email FROM people WHERE {exclude_test_people('email')}"
        ).fetchall()
        emails = {r[0] for r in rows}
        # real + NULL + empty kept; note testcompany.com is NOT testco.com
        self.assertEqual(emails, {"real.person@acme.com", "hr@testcompany.com", None, ""})
        for bad in ("emp_run_123@testco.com", "hr_run_9@testco.com",
                    "emp_uxfix_1@testco.com", "emp_f17_20260613@testco.com"):
            self.assertNotIn(bad, emails)

    def test_real_testcompany_demo_not_caught(self):
        # Guard: the demo domain @testcompany.com must survive (zero overlap with @testco.com).
        rows = self.con.execute(
            f"SELECT email FROM people WHERE email = 'hr@testcompany.com' AND {exclude_test_people('email')}"
        ).fetchall()
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
