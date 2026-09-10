"""BUG-260909-E7B1 — GET /fields runs blank-only prefill when the pack is empty."""
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
from backend.app.routers.cases_read import get_form_fields  # noqa: E402

SCHEMA = """
CREATE TABLE cases (id TEXT PRIMARY KEY, company_id TEXT, employee_id TEXT);
CREATE TABLE form_templates (
  id TEXT PRIMARY KEY, code TEXT, name TEXT, country TEXT,
  authority_code TEXT, authority_name TEXT, category TEXT,
  version TEXT DEFAULT '1', fields TEXT DEFAULT '[]', sections TEXT DEFAULT '[]',
  source_language TEXT DEFAULT 'en', original_pdf_url TEXT
);
CREATE TABLE case_forms (
  id TEXT PRIMARY KEY, case_id TEXT, form_template_id TEXT,
  person_id TEXT, dependent_id TEXT, status TEXT DEFAULT 'not_started',
  completion_pct INTEGER DEFAULT 0, deadline TEXT, deadline_trigger TEXT,
  blocker_form_id TEXT, original_file_url TEXT, draft_pdf_url TEXT,
  submitted_at TEXT, receipt_ref TEXT, rejection_reason TEXT,
  is_adhoc INTEGER DEFAULT 0, adhoc_name TEXT, adhoc_authority TEXT, notes TEXT,
  created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
  id TEXT PRIMARY KEY, case_form_id TEXT, field_id TEXT,
  value TEXT, filled_by TEXT, ai_confidence REAL, source TEXT,
  reviewed INTEGER DEFAULT 0, overridden INTEGER DEFAULT 0
);
"""


def _u() -> str:
    return str(uuid.uuid4())


class LazyPrefillOnGetFieldsTests(unittest.TestCase):
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
        id_patch = mock.patch.object(
            cases_read_module, "resolve_case_forms_case_id", side_effect=lambda x: x
        )
        id_patch.start()
        self.addCleanup(id_patch.stop)
        access_patch = mock.patch.object(
            cases_read_module, "_assert_case_access", side_effect=lambda u, c: c
        )
        access_patch.start()
        self.addCleanup(access_patch.stop)

        self.case_id, self.form_id, self.tid = _u(), _u(), _u()
        fields = json.dumps([
            {"id": "legal_name", "label": "Full name", "type": "text",
             "required": True, "position": 0,
             "prefill_source": "profile.legal_full_name"},
        ])
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id) VALUES (:i)"), {"i": self.case_id}
            )
            conn.execute(
                text(
                    "INSERT INTO form_templates (id, code, name, country, fields) "
                    "VALUES (:i,'EEA-REG','EEA registration','NO',:f)"
                ),
                {"i": self.tid, "f": fields},
            )
            conn.execute(
                text(
                    "INSERT INTO case_forms (id, case_id, form_template_id) "
                    "VALUES (:i,:c,:t)"
                ),
                {"i": self.form_id, "c": self.case_id, "t": self.tid},
            )

    def test_get_fields_runs_prefill_when_slots_are_blank(self) -> None:
        with mock.patch.object(cases_read_module, "run_prefill", return_value=1) as prefill:
            get_form_fields(self.case_id, self.form_id, {"id": "e", "role": "EMPLOYEE"})
        prefill.assert_called_once_with(self.form_id, self.case_id)

    def test_get_fields_skips_prefill_when_already_filled(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO case_form_field_values "
                    "(id, case_form_id, field_id, value, filled_by) "
                    "VALUES (:i,:f,'legal_name','Ada','system')"
                ),
                {"i": _u(), "f": self.form_id},
            )
        with mock.patch.object(cases_read_module, "run_prefill", return_value=0) as prefill:
            items = get_form_fields(
                self.case_id, self.form_id, {"id": "e", "role": "EMPLOYEE"}
            )
        prefill.assert_not_called()
        self.assertEqual(items[0].value, "Ada")
