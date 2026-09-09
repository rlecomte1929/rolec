"""
Phase 2b — cross-form write-back propagation.

When a user fills a source-backed (profile./contract./banking.) field on the data sheet, the
value is written back to cases.intake_data so prefill_engine re-derives it into EVERY other form
on their next prefill — "capture once, reuse everywhere". This is the propagation the Phase 2
acceptance calls for ("a second surface shows the same value without re-entry"), across forms.

Two guarantees:
  1. Edit form A (data_sheet) → a SEPARATE form B prefills the same value with real provenance.
  2. Write-back targets the intake sub-key already in use (e.g. 'employment'), never a fresh
     'contract' dict that would shadow it and blank the sibling fields.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from backend.app.services import prefill_engine  # noqa: E402
from backend.app.services.prefill_engine import run_prefill  # noqa: E402
from backend.app.routers import data_sheet as data_sheet_router  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402
from backend.main import app  # noqa: E402
from tests.test_prefill_engine import (  # noqa: E402
    SCHEMA, _insert_case, _insert_case_form, _uuid,
)

EMPLOYEE = {"id": "emp-1", "role": "EMPLOYEE"}

SHEET_FIELDS = [
    {"id": "emp_name", "section": "emp", "label": "Employer", "type": "text",
     "prefill_source": "contract.employer_name", "position": 1},
    {"id": "org_no", "section": "emp", "label": "Org number", "type": "text",
     "prefill_source": "contract.employer_org_number", "position": 2},
]
# A second, non-data-sheet form that reads the same contract.* paths.
FORM_B_FIELDS = [
    {"id": "b_name", "label": "Employer", "type": "text", "prefill_source": "contract.employer_name", "position": 1},
    {"id": "b_org", "label": "Org number", "type": "text", "prefill_source": "contract.employer_org_number", "position": 2},
]


class DataSheetWriteBackPropagation(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN category TEXT"))
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN sections TEXT DEFAULT '[]'"))
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN authority_name TEXT"))

        self.patcher = mock.patch.object(prefill_engine.db, "engine", self.engine)
        self.patcher.start()

        app.dependency_overrides[get_current_user] = lambda: EMPLOYEE
        self._orig_access = data_sheet_router._assert_case_access
        data_sheet_router._assert_case_access = lambda user, cid: cid
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(get_current_user, None)
        data_sheet_router._assert_case_access = self._orig_access
        self.patcher.stop()
        self.engine.dispose()

    def _seed(self, intake):
        """Seed a case + a data-sheet form A (prefilled). Returns (case_id, form_a_id)."""
        case_id, emp_id, cf_a, tmpl_a = _uuid(), _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake, dest="NO", origin="FR")
            conn.execute(text(
                "INSERT INTO form_templates (id, code, fields, source_language, category) "
                "VALUES (:id, 'RP-SHEET', :f, 'en', 'data_sheet')"
            ), {"id": tmpl_a, "f": json.dumps(SHEET_FIELDS)})
            _insert_case_form(conn, cf_a, case_id, tmpl_a, person_id=emp_id)
        run_prefill(cf_a, case_id)
        return case_id, cf_a

    def _intake(self, case_id):
        with self.engine.begin() as conn:
            raw = conn.execute(text("SELECT intake_data FROM cases WHERE id=:id"), {"id": case_id}).scalar()
        return json.loads(raw)

    def _prefill_form_b(self, case_id):
        """Create form B and prefill it from the (now-updated) intake. Returns its values."""
        cf_b, tmpl_b = _uuid(), _uuid()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO form_templates (id, code, fields, source_language) VALUES (:id, 'RP-B', :f, 'en')"
            ), {"id": tmpl_b, "f": json.dumps(FORM_B_FIELDS)})
            _insert_case_form(conn, cf_b, case_id, tmpl_b)
        run_prefill(cf_b, case_id)
        with self.engine.begin() as conn:
            rows = conn.execute(text(
                "SELECT field_id, value, source FROM case_form_field_values WHERE case_form_id=:cf"
            ), {"cf": cf_b}).mappings().all()
        return {r["field_id"]: dict(r) for r in rows}

    def _patch(self, case_id, field_id, value):
        return self.client.patch(
            f"/api/cases/{case_id}/datasheet/fields/{field_id}", json={"value": value},
        )

    def test_edit_propagates_to_a_separate_form_via_intake(self):
        # employer_org_number is missing from intake → needs_input on the sheet.
        case_id, _ = self._seed({"contract": {"employer_name": "Acme AS"}})
        resp = self._patch(case_id, "org_no", "999888777")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 1. It landed in the canonical intake store, beside the untouched employer_name.
        intake = self._intake(case_id)
        self.assertEqual(intake["contract"]["employer_org_number"], "999888777")
        self.assertEqual(intake["contract"]["employer_name"], "Acme AS")

        # 2. A brand-new form prefills the value with real provenance — no re-entry.
        b = self._prefill_form_b(case_id)
        self.assertEqual(b["b_org"]["value"], "999888777")
        self.assertEqual(b["b_org"]["source"], "contract")
        self.assertEqual(b["b_name"]["value"], "Acme AS")

    def test_writeback_targets_the_aliased_subkey_without_shadowing(self):
        # This case stores its contract data under the 'employment' alias, not 'contract'.
        case_id, _ = self._seed({"employment": {"employer_name": "Beta AS"}})
        resp = self._patch(case_id, "org_no", "111222333")
        self.assertEqual(resp.status_code, 200, resp.text)

        intake = self._intake(case_id)
        # Written into the SAME sub-key prefill reads; no shadowing 'contract' dict created.
        self.assertEqual(intake["employment"]["employer_org_number"], "111222333")
        self.assertEqual(intake["employment"]["employer_name"], "Beta AS")
        self.assertNotIn("contract", intake)

        # The sibling field still resolves for a downstream form (proves no shadowing).
        b = self._prefill_form_b(case_id)
        self.assertEqual(b["b_name"]["value"], "Beta AS")
        self.assertEqual(b["b_org"]["value"], "111222333")

    def test_free_text_field_stays_form_local(self):
        # A field with no prefill_source must NOT touch intake_data.
        case_id, cf_a = self._seed({"contract": {"employer_name": "Acme AS"}})
        # Add an unsourced field to form A's template on the fly.
        with self.engine.begin() as conn:
            fields = SHEET_FIELDS + [{"id": "note", "section": "emp", "label": "Note", "type": "text", "position": 3}]
            conn.execute(text(
                "UPDATE form_templates SET fields=:f WHERE id=(SELECT form_template_id FROM case_forms WHERE id=:cf)"
            ), {"f": json.dumps(fields), "cf": cf_a})
        before = self._intake(case_id)
        resp = self._patch(case_id, "note", "bring the lease")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._intake(case_id), before)  # intake untouched


if __name__ == "__main__":
    unittest.main()
