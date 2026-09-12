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

from backend.db.test_data_filter import (  # noqa: E402
    exclude_test_companies,
    exclude_test_people,
    exclude_test_prospects,
    looks_like_test_company,
    looks_like_test_email,
    looks_like_test_prospect,
    strip_verify_prefix,
)


class TestDataFilterTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(
            """
            CREATE TABLE companies (name TEXT);
            INSERT INTO companies (name) VALUES
              ('Acme GmbH'), ('Globex'), ('Testing April'),
              ('Other Corp'), ('Test Co (Seed)'), ('Test company'),
              ('Other Corp (Seed)'), ('Probe ISO-A'), ('Probe ISO-B'),
              ('Brand New Co 1782553314571'), ('Test Drive Romain a1b2'), (NULL);
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
        # every synthetic name gone (incl. Wave-3 'Brand New Co <epoch>' — AIQ-1325a)
        for bad in ("Other Corp", "Test Co (Seed)", "Test company",
                    "Other Corp (Seed)", "Probe ISO-A", "Probe ISO-B",
                    "Brand New Co 1782553314571", "Test Drive Romain a1b2"):
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

    def test_test_drive_company_flagged_at_write_time(self):
        # Test-drive provisioning creates 'Test Drive <name> <suffix>' companies; these
        # must be auto-stamped is_test=true so they don't pollute admin surfaces.
        self.assertTrue(looks_like_test_company("Test Drive Romain a1b2"))
        # Guard: a real tenant that merely contains the word 'Drive' is not caught.
        self.assertFalse(looks_like_test_company("Drive Logistics GmbH"))

    def test_real_testcompany_demo_not_caught(self):
        # Guard: the demo domain @testcompany.com must survive (zero overlap with @testco.com).
        rows = self.con.execute(
            f"SELECT email FROM people WHERE email = 'hr@testcompany.com' AND {exclude_test_people('email')}"
        ).fetchall()
        self.assertEqual(len(rows), 1)


class ExtendedSeederFilterTests(unittest.TestCase):
    """AIQ-2327 — the newer seeder families the AIQ-913 filter predates."""

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript(
            """
            CREATE TABLE companies (name TEXT);
            INSERT INTO companies (name) VALUES
              ('Google'), ('Google Dublin'), ('Testing April'), ('Meridian Capital'),
              ('GlobalTech SAS'), ('Nexora Labs'), ('SLB Denis'), ('SLB_Denis'), ('Wave1 Tech'),
              ('Google IE Q1786637682758'), ('Google Ireland T18-A-1786634420882'),
              ('CPY Abe Romo'), ('VCo 1786634558409'), ('WCo 1786634597516'),
              ('Company 1'), ('TestCompany'), ('YvesTestCompany');
            CREATE TABLE people (email TEXT);
            INSERT INTO people (email) VALUES
              ('real.person@acme.com'), ('romain_lecomte@hotmail.com'),
              ('qa-proj-relopass-com-mtajn62l@reloulexei.resend.app'),
              ('jane.smith@example.com'), ('roma+t18empb_1789@hotmail.com'),
              ('roma+emp_run_5@hotmail.com');
            """
        )

    def tearDown(self):
        self.con.close()

    def test_new_seeder_companies_excluded_demo_kept(self):
        rows = self.con.execute(
            f"SELECT name FROM companies WHERE {exclude_test_companies('name')}"
        ).fetchall()
        names = {r[0] for r in rows}
        self.assertEqual(names, {
            "Google", "Google Dublin", "Testing April", "Meridian Capital",
            "GlobalTech SAS", "Nexora Labs", "SLB Denis", "SLB_Denis", "Wave1 Tech",
        })

    def test_new_seeder_emails_excluded_real_kept(self):
        rows = self.con.execute(
            f"SELECT email FROM people WHERE {exclude_test_people('email')}"
        ).fetchall()
        emails = {r[0] for r in rows}
        # The real address + Romain's own un-aliased hotmail survive.
        self.assertEqual(emails, {"real.person@acme.com", "romain_lecomte@hotmail.com"})

    def test_write_time_classifiers(self):
        for bad in ("Google IE Q1786637682758", "Google Ireland T18-A-1786634420882",
                    "CPY Abe Romo", "VCo 1786634558409", "Company 1", "YvesTestCompany"):
            self.assertTrue(looks_like_test_company(bad), bad)
        for good in ("Google", "Google Dublin", "Testing April", "Meridian Capital",
                     "GlobalTech SAS", "Nexora Labs", "Wave1 Tech"):
            self.assertFalse(looks_like_test_company(good), good)
        for bad in ("qa-proj-x@reloulexei.resend.app", "jane@example.com",
                    "roma+t18empb_1@hotmail.com", "roma+emp_run_5@hotmail.com"):
            self.assertTrue(looks_like_test_email(bad), bad)
        self.assertFalse(looks_like_test_email("romain_lecomte@hotmail.com"))

    def test_qa_prospects_excluded(self):
        self.con.executescript(
            """
            CREATE TABLE prospects (company_name TEXT);
            INSERT INTO prospects (company_name) VALUES
              ('Acme GmbH'), ('QA Corp'), ('Bob Dylan Company'),
              ('HR Dir @ Acme'), ('A test school');
            """
        )
        rows = self.con.execute(
            f"SELECT company_name FROM prospects WHERE {exclude_test_prospects('company_name')}"
        ).fetchall()
        self.assertEqual({r[0] for r in rows}, {"Acme GmbH"})
        self.assertTrue(looks_like_test_prospect("QA Corp"))
        self.assertFalse(looks_like_test_prospect("Acme GmbH"))


class StripVerifyPrefixTests(unittest.TestCase):
    """AIQ-1325b — read-time scrub of the '[verify]' marker from inbox text."""

    def test_strips_leading_marker_and_space(self):
        self.assertEqual(strip_verify_prefix("[verify] Hello"), "Hello")

    def test_case_insensitive(self):
        self.assertEqual(strip_verify_prefix("[VERIFY] x"), "x")

    def test_no_space_after_marker(self):
        self.assertEqual(strip_verify_prefix("[verify]Hello"), "Hello")

    def test_collapses_extra_leading_whitespace(self):
        self.assertEqual(strip_verify_prefix("[verify]   spaced"), "spaced")

    def test_normal_text_unchanged(self):
        self.assertEqual(strip_verify_prefix("Your relocation case is ready"),
                         "Your relocation case is ready")

    def test_marker_only_when_leading(self):
        # Not at the start → left alone.
        self.assertEqual(strip_verify_prefix("re: [verify] later"), "re: [verify] later")

    def test_none_and_empty_passthrough(self):
        self.assertIsNone(strip_verify_prefix(None))
        self.assertEqual(strip_verify_prefix(""), "")


if __name__ == "__main__":
    unittest.main()
