"""
[P4-3] Tests for the ad-hoc "Add document" endpoints.

Mirrors test_case_dossier_forms.py: in-memory SQLite engine with the needed
table shapes, mock `main_db.engine`, call the async router functions directly
(via asyncio.run) to bypass FastAPI DI and multipart parsing.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import unittest
import uuid
from unittest import mock

from starlette.datastructures import Headers

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases as cases_module  # noqa: E402
from backend.app.routers import case_forms_adhoc as adhoc_module  # noqa: E402
from backend.app.routers.case_forms_adhoc import (  # noqa: E402
    create_adhoc_form,
    replace_adhoc_pdf,
)
from backend.app.routers.cases import (  # noqa: E402
    list_case_forms,
    create_dossier,
    CreateDossierPayload,
)
from fastapi import HTTPException, UploadFile  # noqa: E402


SCHEMA = """
CREATE TABLE cases (
  id           TEXT PRIMARY KEY,
  company_id   TEXT,
  employee_id  TEXT,
  hr_owner_id  TEXT
);
CREATE TABLE profiles (
  id         TEXT PRIMARY KEY,
  email      TEXT,
  full_name  TEXT,
  company_id TEXT
);
CREATE TABLE case_dependents (
  id            TEXT PRIMARY KEY,
  case_id       TEXT NOT NULL,
  relationship  TEXT NOT NULL,
  full_name     TEXT
);
CREATE TABLE form_templates (
  id              TEXT PRIMARY KEY,
  code            TEXT NOT NULL,
  name            TEXT NOT NULL,
  country         TEXT NOT NULL,
  authority_code  TEXT,
  authority_name  TEXT,
  category        TEXT,
  version         TEXT NOT NULL DEFAULT '1.0.0',
  fields          TEXT NOT NULL DEFAULT '[]',
  trigger_rules   TEXT NOT NULL DEFAULT '[]',
  source_url      TEXT,
  verification_status TEXT DEFAULT 'representative'
);
CREATE TABLE roadmap_steps (
  id       TEXT PRIMARY KEY,
  case_id  TEXT,
  title    TEXT
);
CREATE TABLE case_forms (
  id                TEXT PRIMARY KEY,
  case_id           TEXT NOT NULL,
  form_template_id  TEXT,
  person_id         TEXT,
  dependent_id      TEXT,
  status            TEXT NOT NULL DEFAULT 'not_started',
  completion_pct    INTEGER NOT NULL DEFAULT 0,
  deadline          TEXT,
  deadline_trigger  TEXT,
  blocker_form_id   TEXT,
  rejection_reason  TEXT,
  roadmap_step_id   TEXT,
  is_adhoc          INTEGER NOT NULL DEFAULT 0,
  adhoc_name        TEXT,
  adhoc_authority   TEXT,
  notes             TEXT,
  original_file_url TEXT,
  draft_pdf_url     TEXT,
  submitted_at      TEXT,
  receipt_ref       TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
  id            TEXT PRIMARY KEY,
  case_form_id  TEXT NOT NULL,
  field_id      TEXT NOT NULL,
  value         TEXT,
  filled_by     TEXT NOT NULL,
  ai_confidence REAL,
  reviewed      INTEGER NOT NULL DEFAULT 0,
  overridden    INTEGER NOT NULL DEFAULT 0,
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_form_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  case_form_id  TEXT NOT NULL,
  event_type    TEXT NOT NULL,
  actor_id      TEXT,
  note          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE dossier_packages (
  id          TEXT PRIMARY KEY,
  case_id     TEXT NOT NULL,
  name        TEXT NOT NULL,
  form_ids    TEXT NOT NULL,
  cover_page  INTEGER NOT NULL DEFAULT 0,
  created_by  TEXT,
  pdf_url     TEXT,
  generated_at TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _u() -> str:
    return str(uuid.uuid4())


def _hr_user(uid: str) -> dict:
    return {"id": uid, "role": "HR", "is_admin": False}


class AdhocFormsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        # Both modules reference main_db.engine; patch both aliases.
        self.p1 = mock.patch.object(cases_module.main_db, "engine", self.engine)
        self.p2 = mock.patch.object(adhoc_module.main_db, "engine", self.engine)
        self.p1.start()
        self.p2.start()
        self.addCleanup(self.p1.stop)
        self.addCleanup(self.p2.stop)
        # No Supabase in tests — storage helper returns None.
        self.p3 = mock.patch.object(adhoc_module, "_store_adhoc_pdf", return_value=None)
        self.p3.start()
        self.addCleanup(self.p3.stop)

        self.company_id = _u()
        self.employee_id = _u()
        self.hr_id = _u()
        self.case_id = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, email, full_name, company_id) "
                     "VALUES (:id, :e, :n, :c)"),
                {"id": self.employee_id, "e": "e@x.com", "n": "Emp", "c": self.company_id},
            )
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id, hr_owner_id) "
                     "VALUES (:id, :c, :e, :h)"),
                {"id": self.case_id, "c": self.company_id, "e": self.employee_id, "h": self.hr_id},
            )

    def _create(self, **kwargs):
        defaults = dict(
            case_id=self.case_id, name="Birth certificate", authority="Town hall",
            person_id=None, deadline=None, notes="bring original",
            file=None, user=_hr_user(self.hr_id),
        )
        defaults.update(kwargs)
        return asyncio.run(create_adhoc_form(**defaults))

    # ── tests ────────────────────────────────────────────────────────────────

    def test_create_adhoc_form_minimal(self) -> None:
        summary = self._create()
        self.assertTrue(summary.is_adhoc)
        self.assertEqual(summary.status, "in_progress")
        self.assertEqual(summary.completion_pct, 0)
        self.assertEqual(summary.template.code, "CUSTOM")
        self.assertEqual(summary.template.name, "Birth certificate")
        self.assertEqual(summary.template.authority_name, "Town hall")
        self.assertEqual(summary.notes, "bring original")
        self.assertEqual(summary.fields_summary.total, 0)

    def test_create_requires_name(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._create(name="   ")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_adhoc_form_appears_in_list_with_custom_badge(self) -> None:
        self._create(name="Marriage cert", authority=None)
        rows = list_case_forms(case_id=self.case_id, status=None, user=_hr_user(self.hr_id))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row.is_adhoc)
        self.assertEqual(row.template.code, "CUSTOM")
        self.assertEqual(row.template.name, "Marriage cert")
        self.assertIsNone(row.template.authority_name)

    def test_adhoc_form_can_be_added_to_dossier_package(self) -> None:
        summary = self._create(name="Lease agreement")
        payload = CreateDossierPayload(
            name="My package", form_ids=[summary.id], cover_page=False
        )
        with mock.patch.object(cases_module, "_try_store_dossier_pdf", return_value=None):
            pkg = create_dossier(
                case_id=self.case_id, payload=payload, user=_hr_user(self.hr_id)
            )
        self.assertIn(summary.id, pkg.form_ids)

    def test_replace_pdf_rejects_non_adhoc(self) -> None:
        # Seed a regular (template-backed) form.
        tid = _u()
        cf_id = _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO form_templates (id, code, name, country) "
                     "VALUES (:id, 'UTL', 'Permit', 'NO')"),
                {"id": tid},
            )
            conn.execute(
                text("INSERT INTO case_forms (id, case_id, form_template_id, status, is_adhoc) "
                     "VALUES (:id, :cid, :tid, 'not_started', 0)"),
                {"id": cf_id, "cid": self.case_id, "tid": tid},
            )
        upload = UploadFile(
            filename="x.pdf",
            file=io.BytesIO(b"%PDF-1.4 data"),
            headers=Headers({"content-type": "application/pdf"}),
        )
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(replace_adhoc_pdf(
                case_id=self.case_id, form_id=cf_id, file=upload, user=_hr_user(self.hr_id)
            ))
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
