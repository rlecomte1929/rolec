"""
[P1-05 / AIQ-199 follow-up] Verifies source_url + roadmap_step_title surface
through the LIVE dossier forms endpoint.

The wired GET /api/cases/{id}/forms handler lives in `cases_read.py` (the
`cases.py` copy is unwired dead code — AUDIT-B9-cases-6). PR #299 mistakenly
only patched the dead copy; this test guards the live path in cases_read.

Pattern mirrors test_case_dossier_forms.py: in-memory SQLite + mocked
main_db.engine, calling the router function directly.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases_read as cases_read_module  # noqa: E402
from backend.app.routers.cases_read import list_case_forms  # noqa: E402


SCHEMA = """
CREATE TABLE cases (
  id TEXT PRIMARY KEY, company_id TEXT, employee_id TEXT, hr_owner_id TEXT
);
CREATE TABLE profiles (
  id TEXT PRIMARY KEY, email TEXT, full_name TEXT, company_id TEXT
);
CREATE TABLE case_dependents (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, relationship TEXT NOT NULL, full_name TEXT
);
CREATE TABLE form_templates (
  id TEXT PRIMARY KEY, code TEXT NOT NULL, name TEXT NOT NULL, country TEXT NOT NULL,
  authority_code TEXT, authority_name TEXT, category TEXT,
  version TEXT NOT NULL DEFAULT '1.0.0', fields TEXT NOT NULL DEFAULT '[]',
  trigger_rules TEXT NOT NULL DEFAULT '[]', source_url TEXT,
  verification_status TEXT DEFAULT 'representative'
);
CREATE TABLE roadmap_steps (
  id TEXT PRIMARY KEY, case_id TEXT, title TEXT
);
CREATE TABLE source_pages (
  id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, tier TEXT, last_fetched_at TEXT
);
CREATE TABLE case_forms (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, form_template_id TEXT,
  person_id TEXT, dependent_id TEXT, status TEXT NOT NULL DEFAULT 'not_started',
  completion_pct INTEGER NOT NULL DEFAULT 0, deadline TEXT, deadline_trigger TEXT,
  blocker_form_id TEXT, rejection_reason TEXT, roadmap_step_id TEXT,
  is_adhoc INTEGER NOT NULL DEFAULT 0, adhoc_name TEXT, adhoc_authority TEXT, notes TEXT,
  original_file_url TEXT, draft_pdf_url TEXT, submitted_at TEXT, receipt_ref TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
  id TEXT PRIMARY KEY, case_form_id TEXT NOT NULL, field_id TEXT NOT NULL,
  value TEXT, filled_by TEXT NOT NULL, ai_confidence REAL,
  reviewed INTEGER NOT NULL DEFAULT 0, overridden INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _u() -> str:
    return str(uuid.uuid4())


def _emp_user(uid: str) -> dict:
    return {"id": uid, "role": "EMPLOYEE", "is_admin": False}


class LiveSourceUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        patcher = mock.patch.object(cases_read_module.main_db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.company_id, self.employee_id, self.case_id = _u(), _u(), _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, email, full_name, company_id) VALUES (:i,:e,:n,:c)"),
                {"i": self.employee_id, "e": "e@x.com", "n": "Marc Bouchard", "c": self.company_id},
            )
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id) VALUES (:i,:c,:e)"),
                {"i": self.case_id, "c": self.company_id, "e": self.employee_id},
            )

    def _seed_form(self, *, source_url, step_title, fields="[]") -> None:
        tid, cfid = _u(), _u()
        step_id = None
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO form_templates (id, code, name, country, fields, source_url) "
                     "VALUES (:i,:c,:n,'NO',:f,:s)"),
                {"i": tid, "c": "GP-7-04", "n": "D-number application", "s": source_url, "f": fields},
            )
            if source_url is not None:
                conn.execute(
                    text("INSERT INTO source_pages (id, url, tier, last_fetched_at) "
                         "VALUES (:i,:u,'1','2026-06-04T10:00:00')"),
                    {"i": _u(), "u": source_url},
                )
            if step_title is not None:
                step_id = _u()
                conn.execute(
                    text("INSERT INTO roadmap_steps (id, case_id, title) VALUES (:i,:c,:t)"),
                    {"i": step_id, "c": self.case_id, "t": step_title},
                )
            conn.execute(
                text("INSERT INTO case_forms (id, case_id, form_template_id, person_id, roadmap_step_id) "
                     "VALUES (:i,:c,:t,:p,:s)"),
                {"i": cfid, "c": self.case_id, "t": tid, "p": self.employee_id, "s": step_id},
            )

    def test_source_url_and_step_title_surface(self) -> None:
        url = "https://www.skatteetaten.no/en/person/foreign/norwegian-identification-number/d-number/"
        self._seed_form(source_url=url, step_title="Register your arrival")
        rows = list_case_forms(case_id=self.case_id, status=None, user=_emp_user(self.employee_id))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].template.source_url, url)
        self.assertEqual(rows[0].roadmap_step_title, "Register your arrival")
        # [P1-05d] last_verified pulled from source_pages.last_fetched_at via the join.
        self.assertEqual(rows[0].template.source_last_verified, "2026-06-04T10:00:00")

    def test_required_documents_derived_from_requires_original_fields(self) -> None:
        # [P1-05 checklist] only fields with requires_original=true become items.
        fields = json.dumps([
            {"id": "passport_number", "label": "Passport number", "requires_original": True},
            {"id": "dob", "label": "Date of birth", "requires_original": False},
            {"id": "marriage_cert", "label": "Marriage certificate", "requires_original": True},
        ])
        self._seed_form(source_url=None, step_title=None, fields=fields)
        rows = list_case_forms(case_id=self.case_id, status=None, user=_emp_user(self.employee_id))
        req = rows[0].template.required_documents
        self.assertEqual(
            [r["key"] for r in req], ["passport_number", "marriage_cert"]
        )
        self.assertEqual(req[0]["label"], "Passport number")

    def test_source_url_null_when_absent(self) -> None:
        # source_url + last_verified are genuinely absent here.
        self._seed_form(source_url=None, step_title=None)
        rows = list_case_forms(case_id=self.case_id, status=None, user=_emp_user(self.employee_id))
        self.assertIsNone(rows[0].template.source_url)
        self.assertIsNone(rows[0].template.source_last_verified)

    def test_step_title_falls_back_to_computed_track_label(self) -> None:
        # [AIQ-800] Option B: with no persisted roadmap step linked, the form-card
        # "Roadmap step" label now falls back to the computed track bucket
        # (previously null). A persisted rs.title still wins when present —
        # see test_source_url_and_step_title_surface.
        from backend.app.services.roadmap_projection import track_label_for_form
        self._seed_form(source_url=None, step_title=None)
        rows = list_case_forms(case_id=self.case_id, status=None, user=_emp_user(self.employee_id))
        # template seeded with code GP-7-04 and no category → default 'Settlement'.
        self.assertEqual(rows[0].roadmap_step_title, track_label_for_form(None, "GP-7-04"))
        self.assertEqual(rows[0].roadmap_step_title, "Settlement")


if __name__ == "__main__":
    unittest.main()
