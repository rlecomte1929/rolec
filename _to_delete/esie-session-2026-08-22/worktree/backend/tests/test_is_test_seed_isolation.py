"""PRODSEED-3 / AIQ-1130 — durable test-data isolation via the is_test flag.

Two halves, both against real SQLite (mirrors test_test_data_filter.py's style):

1. The write-time classifiers (looks_like_test_company / looks_like_test_email)
   correctly flag every synthetic seeder signature AND leave the demo tenants
   (Testing April / @testcompany.com / @testingapril.com) and real rows alone.
2. The read-time filter SQL (COALESCE(is_test, false) = false) hides flagged
   rows and keeps real + demo rows — the contract get_admin_company_index and
   get_admin_people_index rely on.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db.test_data_filter import (  # noqa: E402
    looks_like_test_company,
    looks_like_test_email,
)


class WriteTimeClassifierTests(unittest.TestCase):
    """The auto-stamp predicates used by create_company / create_profile."""

    def test_synthetic_company_names_flagged(self):
        for name in (
            "Other Corp",
            "Test Co (Seed)",
            "Other Corp (Seed)",
            "Test company",
            "Probe ISO-A",
            "Probe RLS-A 1718000000",
            "Probe RLS-B 1718000000",
            "Brand New Co 1782553314571",  # Wave-3 onboarding e2e (AIQ-1325a)
        ):
            self.assertTrue(looks_like_test_company(name), f"{name!r} should be test")

    def test_demo_and_real_companies_not_flagged(self):
        # The demo tenant and ordinary customers must never be hidden.
        # 'Brand New Company GmbH' must NOT match the tight 'Brand New Co ' prefix.
        for name in ("Testing April", "Acme GmbH", "Globex", "Probe Industries",
                     "Brand New Company GmbH", "", None):
            self.assertFalse(looks_like_test_company(name), f"{name!r} should be real")

    def test_synthetic_emails_flagged(self):
        for email in (
            "emp_run_123@testco.com",
            "hr_run_9@testco.com",
            "emp_uxfix_1@testco.com",
            "EMP_F17_20260613@TESTCO.COM",  # case-insensitive
            "probe-rls-a-1718@probe.test",
        ):
            self.assertTrue(looks_like_test_email(email), f"{email!r} should be test")

    def test_demo_and_real_emails_not_flagged(self):
        # @testcompany.com / @testingapril.com end in '…company.com' / '…april.com',
        # NOT '@testco.com' — they must stay visible.
        for email in (
            "hr@testcompany.com",
            "employee@testingapril.com",
            "real.person@acme.com",
            "",
            None,
        ):
            self.assertFalse(looks_like_test_email(email), f"{email!r} should be real")


class ReadFilterSqlTests(unittest.TestCase):
    """The COALESCE(is_test, false) = false predicate over a real is_test column."""

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(
            """
            CREATE TABLE companies (name TEXT, is_test BOOLEAN DEFAULT 0);
            INSERT INTO companies (name, is_test) VALUES
              ('Acme GmbH', 0),          -- real
              ('Testing April', 0),      -- demo (must stay visible)
              ('Test company', 1),       -- synthetic (flagged)
              ('Probe RLS-A 1', 1);      -- synthetic (flagged)
            CREATE TABLE profiles (email TEXT, is_test BOOLEAN DEFAULT 0);
            INSERT INTO profiles (email, is_test) VALUES
              ('real.person@acme.com', 0),
              ('hr@testcompany.com', 0),     -- demo
              ('emp_run_1@testco.com', 1),   -- synthetic
              ('probe-rls-a@probe.test', 1); -- synthetic
            """
        )

    def tearDown(self):
        self.con.close()

    def test_company_filter_hides_only_flagged(self):
        rows = self.con.execute(
            "SELECT name FROM companies WHERE COALESCE(is_test, 0) = 0 ORDER BY name"
        ).fetchall()
        names = [r[0] for r in rows]
        self.assertEqual(names, ["Acme GmbH", "Testing April"])

    def test_people_filter_hides_only_flagged(self):
        rows = self.con.execute(
            "SELECT email FROM profiles WHERE COALESCE(is_test, 0) = 0 ORDER BY email"
        ).fetchall()
        emails = [r[0] for r in rows]
        self.assertEqual(emails, ["hr@testcompany.com", "real.person@acme.com"])

    def test_include_test_shows_everything(self):
        n = self.con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        self.assertEqual(n, 4)


if __name__ == "__main__":
    unittest.main()
