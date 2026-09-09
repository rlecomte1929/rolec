"""
GET /api/cases/{case_id}/datasheet/pdf — Phase 3 export endpoint test.

Exports the composed data sheet as a print-grade PDF (render_data_sheet). Seeds the golden FR→NO
case exactly like test_datasheet_endpoint, then asserts the endpoint streams a real PDF.
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
    SCHEMA, _insert_case, _insert_case_form, _insert_profile, _uuid,
)
from tests.test_golden_case_fr_no_datasheet import (  # noqa: E402
    GOLDEN_CASE_COLUMNS, GOLDEN_INTAKE, _template_fields_from_migration,
)

EMPLOYEE = {"id": "emp-1", "role": "EMPLOYEE"}


class DataSheetPdfEndpoint(unittest.TestCase):

    def setUp(self):
        self.fields = _template_fields_from_migration()
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
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN name TEXT"))

        self.patcher = mock.patch.object(prefill_engine.db, "engine", self.engine)
        self.patcher.start()

        self.case_id, self.emp_id, self.cf_id, tmpl = _uuid(), _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, self.case_id, self.emp_id, GOLDEN_INTAKE,
                         dest="NO", origin="FR", **GOLDEN_CASE_COLUMNS)
            _insert_profile(conn, self.emp_id, full_name="Camille Moreau")
            conn.execute(text(
                "INSERT INTO form_templates (id, code, name, fields, source_language, category, authority_name) "
                "VALUES (:id, 'RP-NO-DATASHEET', 'Personal Relocation Data Sheet', :f, 'nb', 'data_sheet', :auth)"
            ), {"id": tmpl, "f": json.dumps(self.fields), "auth": "ReloPass"})
            _insert_case_form(conn, self.cf_id, self.case_id, tmpl, person_id=self.emp_id)
        run_prefill(self.cf_id, self.case_id)

        app.dependency_overrides[get_current_user] = lambda: EMPLOYEE
        self._orig_access = data_sheet_router._assert_case_access
        data_sheet_router._assert_case_access = lambda user, cid: cid
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(get_current_user, None)
        data_sheet_router._assert_case_access = self._orig_access
        self.patcher.stop()
        self.engine.dispose()

    def test_pdf_export_streams_a_real_pdf(self):
        resp = self.client.get(f"/api/cases/{self.case_id}/datasheet/pdf")
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))
        self.assertTrue(resp.content.startswith(b"%PDF"), "response is not a PDF document")
        self.assertGreater(len(resp.content), 1000, "PDF is suspiciously small")

    def test_no_datasheet_form_returns_404(self):
        resp = self.client.get(f"/api/cases/{_uuid()}/datasheet/pdf")
        self.assertEqual(resp.status_code, 404, resp.text[:300])


if __name__ == "__main__":
    unittest.main()
