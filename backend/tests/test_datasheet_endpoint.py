"""
GET /api/cases/{case_id}/datasheet — Phase 1 endpoint test.

Surfaces, through HTTP, the exact guarantee the data-layer golden test
(test_golden_case_fr_no_datasheet.py) already pins: on the golden FR→NO case (Camille Moreau)
the composed sheet returns the 5 sections, every sourced field carries its golden value with a
real provenance, and the 5 consult-professional determinations are blank with guidance only.

Harness note: the data-sheet service and prefill_engine both bind the SAME `backend.database.db`
object (mocked by backend/conftest.py). Patching `prefill_engine.db.engine` to the in-memory
SQLite therefore points the service's reads at the same engine the fixtures seed — no separate
Database() needed. Access control is exercised elsewhere; here `_assert_case_access` is a
passthrough so the test stays focused on composition.
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

EMPLOYEE = {"id": "emp-1", "email": "e@example.com", "role": "EMPLOYEE"}

# The five sections of RP-NO-DATASHEET, in encounter order.
EXPECTED_SECTIONS = ["d_number", "eea_registration", "skattekort", "folkeregister", "a1"]

# The sourced identifiers keyed by the GOVERNED fact_key (not the template field id).
EXPECTED_BY_FACT = {
    "full_name": "Camille Moreau",
    "date_of_birth": "1990-04-17",
    "nationality": "FR",
    "passport_number": "18AB45678",
    "passport_expiry": "2031-06-30",
    "employer_name": "Nordisk Teknologi AS",
    "employer_org_number": "923456789",
    "job_title": "Senior Software Engineer",
    "employment_start_date": "2026-09-15",
    "salary_amount": "780000",
    "arrival_date": "2026-09-01",
    "intended_stay_months": "18",
}

# The five regulated determinations that must never carry a value.
CONSULT_FACTS = {
    "tax_residency_status", "shadow_payroll_requirement", "pe_risk",
    "a1_determination", "contract_classification",
}


class DataSheetEndpoint(unittest.TestCase):

    def setUp(self):
        self.fields = _template_fields_from_migration()
        # StaticPool = one shared connection, so the single in-memory DB the fixtures seed is
        # the same one the TestClient's worker thread reads at request time.
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
            # Add the prod form_templates columns the data-sheet service reads (the shared
            # prefill SCHEMA omits them). SQLite ADD COLUMN keeps this prod-faithful.
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN category TEXT"))
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN sections TEXT DEFAULT '[]'"))
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN authority_name TEXT"))

        # Point the shared db (prefill + data_sheet_service) at this engine.
        self.patcher = mock.patch.object(prefill_engine.db, "engine", self.engine)
        self.patcher.start()

        self.case_id, self.emp_id, self.cf_id, tmpl = _uuid(), _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, self.case_id, self.emp_id, GOLDEN_INTAKE,
                         dest="NO", origin="FR", **GOLDEN_CASE_COLUMNS)
            _insert_profile(conn, self.emp_id, full_name="Camille Moreau")
            conn.execute(text(
                "INSERT INTO form_templates (id, code, fields, source_language, category, authority_name) "
                "VALUES (:id, :code, :fields, 'nb', 'data_sheet', :auth)"
            ), {"id": tmpl, "code": "RP-NO-DATASHEET",
                "fields": json.dumps(self.fields), "auth": "ReloPass"})
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

    def _get(self, **params):
        resp = self.client.get(f"/api/cases/{self.case_id}/datasheet", params=params)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    @staticmethod
    def _fields_by_fact(data):
        out = {}
        for section in data["sections"]:
            for f in section["fields"]:
                if f.get("factKey"):
                    out[f["factKey"]] = f
        return out

    # ── the composition guarantees ──────────────────────────────────────────

    def test_five_sections_in_order(self):
        data = self._get()
        self.assertTrue(data["covered"])
        self.assertEqual([s["stepId"] for s in data["sections"]], EXPECTED_SECTIONS)

    def test_zero_wrong_every_sourced_value_matches_golden(self):
        by_fact = self._fields_by_fact(self._get())
        wrong = {
            fk: (by_fact.get(fk, {}).get("value"), expected)
            for fk, expected in EXPECTED_BY_FACT.items()
            if by_fact.get(fk, {}).get("value") != expected
        }
        self.assertEqual(wrong, {}, f"values differ from the golden case (got, expected): {wrong}")

    def test_sourced_fields_carry_a_real_provenance(self):
        by_fact = self._fields_by_fact(self._get())
        for fk in EXPECTED_BY_FACT:
            self.assertIn(by_fact[fk]["source"], {"intake", "passport_ocr", "prior_form"},
                          f"{fk} has no real provenance: {by_fact[fk]['source']}")

    def test_consult_determinations_blank_with_guidance(self):
        data = self._get()
        by_fact = self._fields_by_fact(data)
        for fk in CONSULT_FACTS:
            self.assertEqual(by_fact[fk]["source"], "consult_professional", fk)
            self.assertIsNone(by_fact[fk]["value"], f"{fk} leaked a value")
        # …and they are surfaced in the top-level consultProfessional list.
        self.assertEqual(len(data["consultProfessional"]), len(CONSULT_FACTS))

    def test_unsourced_field_is_needs_input_not_guessed(self):
        by_fact = self._fields_by_fact(self._get())
        addr = by_fact["destination_address"]
        self.assertEqual(addr["source"], "needs_input")
        self.assertIsNone(addr["value"])

    def test_completion_math(self):
        data = self._get()
        # 12 sourced (all filled) + 1 needs_input (destination_address); consult excluded.
        self.assertEqual(data["needsInputCount"], 1)
        self.assertEqual(data["completionPct"], 92)

    def test_case_metadata(self):
        data = self._get()
        self.assertEqual(data["employeeName"], "Camille Moreau")
        self.assertEqual(data["corridor"], "FR_NO")
        self.assertIsInstance(data["banners"], list)  # best-effort enrichment

    def test_lang_local_prefers_norwegian_label(self):
        en = self._fields_by_fact(self._get(lang="en"))
        local = self._fields_by_fact(self._get(lang="local"))
        self.assertEqual(en["date_of_birth"]["label"], "Date of birth")
        self.assertEqual(local["date_of_birth"]["label"], "Fodselsdato")

    def test_sparse_mode_returns_only_needs_input(self):
        data = self._get(mode="sparse")
        remaining = [f for s in data["sections"] for f in s["fields"]]
        self.assertTrue(remaining)
        self.assertTrue(all(f["source"] == "needs_input" for f in remaining))
        self.assertEqual({f["factKey"] for f in remaining}, {"destination_address"})

    def test_no_datasheet_form_returns_not_covered(self):
        # A case with no data-sheet case_form must not render an empty sheet as "done".
        resp = self.client.get(f"/api/cases/{_uuid()}/datasheet")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertFalse(body["covered"])
        self.assertEqual(body["sections"], [])


if __name__ == "__main__":
    unittest.main()
