"""
GET /api/cases/{case_id}/datasheet — corridor-content fallback (Option A).

When a case's destination has curated corridor content but NO authored data-sheet template, the
endpoint renders a read-only PREVIEW sheet from `data/corridor-content/<ISO>.ndjson` instead of
"not available yet": one section per curated step (authority-headed, portal linked), the 4-part
non-obvious "moat" banners, and the consult-professional panel. Nothing is fillable (`preview`),
so every non-consult step is `needs_input` with no value.

This test runs over the REAL DE corpus (the fallback loader reads the repo's data/ files), so it
verifies the record→DTO mapping against live data, deriving expected counts from the file itself
rather than hard-coding them.
"""
from __future__ import annotations

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
from backend.app.services import corridor_content  # noqa: E402
from backend.app.routers import data_sheet as data_sheet_router  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402
from backend.main import app  # noqa: E402
from tests.test_prefill_engine import SCHEMA, _insert_case, _uuid  # noqa: E402

EMPLOYEE = {"id": "emp-1", "email": "e@example.com", "role": "EMPLOYEE"}
HR = {"id": "hr-1", "email": "hr@example.com", "role": "HR"}
DEST = "DE"
MOVE_DATE = "2026-10-01"


class DataSheetCorridorContentFallback(unittest.TestCase):

    def setUp(self):
        self.records = corridor_content.load_corridor_content(DEST)
        self.assertTrue(self.records, "DE corridor-content must exist for this test")
        self.consult = [r for r in self.records if r.get("consult_professional")]
        self.non_obvious = [r for r in self.records if r.get("is_non_obvious")]
        self.fillable = [r for r in self.records if not r.get("consult_professional")]

        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
            # form_templates carries the prod columns the service reads (there is no data_sheet
            # row for this case, but the service still SELECTs these columns when it looks).
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN category TEXT"))
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN sections TEXT DEFAULT '[]'"))
            conn.execute(text("ALTER TABLE form_templates ADD COLUMN authority_name TEXT"))

        self.patcher = mock.patch.object(prefill_engine.db, "engine", self.engine)
        self.patcher.start()

        self.case_id, self.emp_id = _uuid(), _uuid()
        with self.engine.begin() as conn:
            # A case bound for DE, with a move date, but deliberately NO data_sheet case_form.
            _insert_case(conn, self.case_id, self.emp_id, {"profile": {"legal_full_name": "Max Müller"}},
                         dest=DEST, origin="US", target_move_date=MOVE_DATE)

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

    # ── the fallback render ──────────────────────────────────────────────────

    def test_renders_a_covered_preview_not_not_covered(self):
        data = self._get()
        self.assertTrue(data["covered"], "corridor content must render, not 'not covered'")
        self.assertTrue(data["preview"], "a template-less sheet is a read-only preview")
        self.assertEqual(data["corridorLabel"], "US→DE")
        self.assertEqual(data["employeeName"], "Max Müller")

    def test_one_section_per_curated_step_each_with_one_field(self):
        data = self._get()
        self.assertEqual(len(data["sections"]), len(self.records))
        for s in data["sections"]:
            self.assertEqual(len(s["fields"]), 1, "each curated step is one section, one field")
            self.assertTrue(s["title"], "the authority heads the step card")
        # Every step that HAS an official portal keeps it clickable (section.sourceUrl); steps
        # with no gov portal (a bank/employer action) legitimately carry none.
        with_portal = sum(1 for s in data["sections"] if s["sourceUrl"])
        self.assertEqual(with_portal, sum(1 for r in self.records if r.get("source_url")))

    def test_nothing_is_prefilled_every_fillable_step_needs_input(self):
        data = self._get()
        self.assertEqual(data["completionPct"], 0)
        self.assertEqual(data["needsInputCount"], len(self.fillable))
        for s in data["sections"]:
            f = s["fields"][0]
            self.assertIn(f["source"], {"needs_input", "consult_professional"})
            self.assertIsNone(f["value"], "a preview never carries a captured value")

    def test_non_obvious_records_become_moat_banners(self):
        data = self._get()
        self.assertEqual(len(data["banners"]), len(self.non_obvious))
        self.assertTrue(all(b["type"] == "moat-fact" for b in data["banners"]))

    def test_consult_records_fill_the_consult_panel_and_stay_blank(self):
        data = self._get()
        self.assertEqual(len(data["consultProfessional"]), len(self.consult))
        consult_fields = [f for s in data["sections"] for f in s["fields"]
                          if f["source"] == "consult_professional"]
        self.assertEqual(len(consult_fields), len(self.consult))
        for f in consult_fields:
            self.assertIsNone(f["value"], "a consult determination is never filled")

    def test_deadlines_are_computed_from_the_move_date(self):
        import datetime as dt
        data = self._get()
        # At least one step carries a deadline offset; it must resolve to move_date + offset.
        by_step = {s["stepId"]: s for s in data["sections"]}
        checked = 0
        for r in self.records:
            offset = r.get("deadline_offset_days")
            if offset is None:
                continue
            fact = r.get("fact_key") or f"{r.get('section')}:{r.get('step')}"
            sid = f"{DEST}:{fact}"
            expected = (dt.date.fromisoformat(MOVE_DATE) + dt.timedelta(days=int(offset))).isoformat()
            self.assertIsNotNone(by_step[sid]["deadline"], f"{sid} lost its deadline")
            self.assertEqual(by_step[sid]["deadline"]["date"], expected)
            checked += 1
        self.assertTrue(checked, "the DE corpus should carry at least one deadline offset")

    def test_hr_view_surfaces_responsible_party(self):
        data = self._get(audience="hr")
        with_party = [s for s in data["sections"] if s["responsibleParty"]]
        self.assertTrue(with_party, "HR view should carry responsible-party annotations")

    def test_employee_view_hides_responsible_party(self):
        data = self._get(audience="employee")
        self.assertTrue(all(s["responsibleParty"] is None for s in data["sections"]))

    def test_sparse_mode_drops_consult_keeps_needs_input(self):
        data = self._get(mode="sparse")
        remaining = [f for s in data["sections"] for f in s["fields"]]
        self.assertTrue(remaining)
        self.assertTrue(all(f["source"] == "needs_input" for f in remaining))
        self.assertEqual(len(remaining), len(self.fillable))

    def test_unknown_destination_still_not_covered(self):
        # A destination with no curated content falls through to the 'not covered' sheet.
        other = _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, other, _uuid(), {}, dest="BR", origin="US")
        resp = self.client.get(f"/api/cases/{other}/datasheet")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertFalse(body["covered"])
        self.assertFalse(body["preview"])
        self.assertEqual(body["sections"], [])


if __name__ == "__main__":
    unittest.main()
