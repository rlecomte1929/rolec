"""
[P1-6 / AIQ-800] Endpoint-level tests for the read-time roadmap projection.

CRITICAL: these import from `backend.app.routers.cases_read` — the LIVE router —
not `backend.app.routers.cases` (dead code, whose tests give false green). They
seed real `case_forms` (NO roadmap_steps rows) and assert that
GET /api/cases/{id}/roadmap/tracks projects them into tracks, and that
GET /api/cases/{id}/forms returns the computed `roadmap_step_title` label.

Harness mirrors test_case_dossier_forms.py: in-memory SQLite + patched
`main_db.engine`, calling the router functions directly to bypass FastAPI DI.
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

from backend.app.routers import cases_read as cr  # noqa: E402
from backend.app.routers.cases_read import (  # noqa: E402
    get_case_roadmap_tracks,
    list_case_forms,
)

# SQLite schema covering every table list_case_forms joins (incl. the LEFT JOINs
# on roadmap_steps + source_pages, which must exist even though Option B no
# longer depends on roadmap_steps being populated).
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
  trigger_rules TEXT NOT NULL DEFAULT '[]', source_url TEXT
);
CREATE TABLE roadmap_steps (id TEXT PRIMARY KEY, case_id TEXT, title TEXT, track_id TEXT);
CREATE TABLE source_pages (url TEXT PRIMARY KEY, last_fetched_at TEXT);
CREATE TABLE case_forms (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, form_template_id TEXT, person_id TEXT,
  dependent_id TEXT, status TEXT NOT NULL DEFAULT 'not_started',
  completion_pct INTEGER NOT NULL DEFAULT 0, deadline TEXT, deadline_trigger TEXT,
  blocker_form_id TEXT, rejection_reason TEXT, roadmap_step_id TEXT,
  is_adhoc INTEGER NOT NULL DEFAULT 0, adhoc_name TEXT, adhoc_authority TEXT, notes TEXT,
  original_file_url TEXT, draft_pdf_url TEXT, submitted_at TEXT, receipt_ref TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
  id TEXT PRIMARY KEY, case_form_id TEXT NOT NULL, field_id TEXT NOT NULL, value TEXT,
  filled_by TEXT NOT NULL, ai_confidence REAL, reviewed INTEGER NOT NULL DEFAULT 0,
  overridden INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _u() -> str:
    return str(uuid.uuid4())


def _emp_user(uid: str) -> dict:
    return {"id": uid, "role": "EMPLOYEE", "is_admin": False}


class RoadmapTracksProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        # main_db is the shared `db` singleton; patching its engine here also
        # reaches case_service._assert_case_access (same object).
        p = mock.patch.object(cr.main_db, "engine", self.engine)
        p.start()
        self.addCleanup(p.stop)

        self.company_id = _u()
        self.employee_id = _u()
        self.case_id = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, email, full_name, company_id) "
                     "VALUES (:i, :e, :n, :c)"),
                {"i": self.employee_id, "e": "e@x.com", "n": "Emp Doe", "c": self.company_id},
            )
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id) VALUES (:i, :c, :e)"),
                {"i": self.case_id, "c": self.company_id, "e": self.employee_id},
            )

    def _template(self, code: str, name: str, category: str) -> str:
        tid = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO form_templates (id, code, name, country, category) "
                     "VALUES (:i, :code, :n, 'NO', :cat)"),
                {"i": tid, "code": code, "n": name, "cat": category},
            )
        return tid

    def _form(self, template_id: str, status: str = "not_started") -> str:
        cf = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_forms (id, case_id, form_template_id, person_id, status) "
                     "VALUES (:i, :c, :t, :p, :s)"),
                {"i": cf, "c": self.case_id, "t": template_id, "p": self.employee_id, "s": status},
            )
        return cf

    def _seed_fr_no(self) -> None:
        self._form(self._template("POL-EEA-REG", "EEA registration", "registration"))
        self._form(self._template("GP-7-04", "D-number", "tax"), status="approved")
        self._form(self._template("APOSTILLE-FR", "Civil apostille", "civil_documents"))

    # ── /roadmap/tracks (criterion #1) ──────────────────────────────────────

    def test_fr_no_forms_project_into_correct_tracks(self) -> None:
        self._seed_fr_no()
        resp = get_case_roadmap_tracks(self.case_id, user=_emp_user(self.employee_id))
        by_key = {t.id: t for t in resp.tracks}

        self.assertEqual(set(by_key), {"visa", "civil", "settlement"})
        self.assertEqual([s.title for s in by_key["visa"].steps], ["EEA registration"])
        self.assertEqual([s.title for s in by_key["civil"].steps], ["Civil apostille"])
        self.assertEqual([s.title for s in by_key["settlement"].steps], ["D-number"])
        # GP-7-04 was approved → step completed → settlement track 100%
        self.assertEqual(by_key["settlement"].steps[0].status, "completed")
        self.assertEqual(by_key["settlement"].progress_pct, 100)
        # tracks ordered by sort_order
        self.assertEqual([t.id for t in resp.tracks], ["visa", "civil", "settlement"])

    def test_no_forms_yields_no_tracks(self) -> None:
        resp = get_case_roadmap_tracks(self.case_id, user=_emp_user(self.employee_id))
        self.assertEqual(resp.tracks, [])

    # ── form-card label (criterion #2) ──────────────────────────────────────

    def test_list_case_forms_computes_roadmap_step_title(self) -> None:
        self._seed_fr_no()
        forms = list_case_forms(case_id=self.case_id, user=_emp_user(self.employee_id))
        labels = {f.template.code: f.roadmap_step_title for f in forms}
        self.assertEqual(labels["POL-EEA-REG"], "Visa & Permit")
        self.assertEqual(labels["GP-7-04"], "Settlement")
        self.assertEqual(labels["APOSTILLE-FR"], "Civil Documents")


if __name__ == "__main__":
    unittest.main()
