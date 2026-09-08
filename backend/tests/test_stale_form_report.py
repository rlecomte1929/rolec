"""[AIQ-1866] Tests for the stale case-form report.

The report is option (a): a read-only cleanup list, never a delete. These tests pin the two
properties that matter — it FLAGS a case_form whose template gate no longer matches the case,
and it NEVER proposes retracting one a human has touched — plus the card's specific trap: a
third-country national in an EEA corridor keeps FAM-SPOUSE and must not be flagged.

Mirrors test_trigger_engine.py: swap db.engine for in-memory SQLite. The schema extends the
trigger harness with the columns the report reads (case_forms.submitted_at, case_form_field_values),
and the persisted draft is injected so re-derivation sees nationality without the ORM.
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

from backend.app.services import stale_form_report as sfr  # noqa: E402

SCHEMA = """
CREATE TABLE cases (
  id TEXT PRIMARY KEY, employee_id TEXT, origin_country_code TEXT,
  dest_country_code TEXT, purpose TEXT
);
CREATE TABLE case_dependents (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, relationship TEXT NOT NULL, full_name TEXT
);
CREATE TABLE form_templates (
  id TEXT PRIMARY KEY, code TEXT NOT NULL, trigger_rules TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_forms (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, form_template_id TEXT NOT NULL,
  person_id TEXT, dependent_id TEXT, status TEXT NOT NULL DEFAULT 'not_started',
  submitted_at TEXT, blocker_form_id TEXT
);
CREATE TABLE case_form_field_values (
  id TEXT PRIMARY KEY, case_form_id TEXT NOT NULL, field_id TEXT NOT NULL,
  value TEXT, filled_by TEXT NOT NULL
);
"""

# Gated: FAM-SPOUSE only for a real permit track (never the EEA registration track).
_GATED = [{"destination_country": "DE", "visa_type": "skilled_worker", "has_spouse": True}]
# Pre-fix / ungated: any DE mover with a spouse — the shape that over-attached on EEA corridors.
_UNGATED = [{"destination_country": "DE", "has_spouse": True}]


def _uuid() -> str:
    return str(uuid.uuid4())


class StaleFormReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        # sfr.db is the shared database.db singleton (same object trigger_engine imports),
        # so patching it here redirects both the report's own queries and the engine helpers.
        patcher = mock.patch.object(sfr.db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ── seeding helpers ──────────────────────────────────────────────────────
    def _case(self, *, origin: str, dest: str = "DE", purpose: str = "work") -> str:
        cid, emp = _uuid(), _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id, employee_id, origin_country_code, "
                     "dest_country_code, purpose) VALUES (:i,:e,:o,:d,:p)"),
                {"i": cid, "e": emp, "o": origin, "d": dest, "p": purpose},
            )
        return cid

    def _spouse(self, case_id: str) -> str:
        did = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_dependents (id, case_id, relationship, full_name) "
                     "VALUES (:i,:c,'spouse','A B')"),
                {"i": did, "c": case_id},
            )
        return did

    def _template(self, code: str, rules: list) -> str:
        tid = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO form_templates (id, code, trigger_rules) VALUES (:i,:c,:r)"),
                {"i": tid, "c": code, "r": json.dumps(rules)},
            )
        return tid

    def _fam_spouse_template(self, *, gated: bool) -> str:
        return self._template("FAM-SPOUSE", [
            {"event": "roadmap.profile_completed", "conditions": c, "for_persons": ["spouse"]}
            for c in (_GATED if gated else _UNGATED)
        ])

    def _attach(self, case_id: str, template_id: str, *, dependent_id: str,
                submitted: bool = False) -> str:
        cf = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_forms (id, case_id, form_template_id, person_id, "
                     "dependent_id, status, submitted_at) VALUES (:i,:c,:t,NULL,:d,'not_started',:s)"),
                {"i": cf, "c": case_id, "t": template_id, "d": dependent_id,
                 "s": "2026-09-01T00:00:00" if submitted else None},
            )
        return cf

    def _field_value(self, case_form_id: str, filled_by: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_form_field_values (id, case_form_id, field_id, value, "
                     "filled_by) VALUES (:i,:c,'f1','x',:b)"),
                {"i": _uuid(), "c": case_form_id, "b": filled_by},
            )

    @staticmethod
    def _eea_mover_draft(_case_id: str) -> dict:
        return {}  # no third-country nationality → EEA free mover

    @staticmethod
    def _third_country_draft(_case_id: str) -> dict:
        return {"employeeProfile": {"nationality": "IN"}}

    # ── tests ────────────────────────────────────────────────────────────────
    def test_a_gated_template_leaves_an_eea_mover_form_stale(self):
        case = self._case(origin="FR")
        dep = self._spouse(case)
        tpl = self._fam_spouse_template(gated=True)
        cf = self._attach(case, tpl, dependent_id=dep)

        stale = sfr.find_stale_case_forms(draft_loader=self._eea_mover_draft)
        self.assertEqual([r["id"] for r in stale], [cf])
        self.assertFalse(stale[0]["gate_still_matches"])
        self.assertEqual(stale[0]["template_code"], "FAM-SPOUSE")
        self.assertTrue(stale[0]["safe_to_retract"])  # no human input, not submitted

    def test_a_third_country_national_in_an_eea_corridor_is_not_flagged(self):
        """The card's trap: FAM-SPOUSE is CORRECT for a third-country national to Germany."""
        case = self._case(origin="FR")
        dep = self._spouse(case)
        tpl = self._fam_spouse_template(gated=True)
        self._attach(case, tpl, dependent_id=dep)

        stale = sfr.find_stale_case_forms(draft_loader=self._third_country_draft)
        self.assertEqual(stale, [])

    def test_an_ungated_template_that_still_matches_is_not_flagged(self):
        case = self._case(origin="FR")
        dep = self._spouse(case)
        tpl = self._fam_spouse_template(gated=False)
        self._attach(case, tpl, dependent_id=dep)

        self.assertEqual(sfr.find_stale_case_forms(draft_loader=self._eea_mover_draft), [])

    def test_a_stale_form_with_human_input_is_flagged_but_never_safe_to_retract(self):
        case = self._case(origin="FR")
        dep = self._spouse(case)
        tpl = self._fam_spouse_template(gated=True)
        cf = self._attach(case, tpl, dependent_id=dep)
        self._field_value(cf, filled_by="employee")

        stale = sfr.find_stale_case_forms(draft_loader=self._eea_mover_draft)
        self.assertEqual(len(stale), 1)
        self.assertTrue(stale[0]["human_input_present"])
        self.assertFalse(stale[0]["auto_filled_only"])
        self.assertFalse(stale[0]["safe_to_retract"])

    def test_an_auto_filled_stale_form_is_safe_but_marked_auto_only(self):
        case = self._case(origin="FR")
        dep = self._spouse(case)
        tpl = self._fam_spouse_template(gated=True)
        cf = self._attach(case, tpl, dependent_id=dep)
        self._field_value(cf, filled_by="ai")

        stale = sfr.find_stale_case_forms(draft_loader=self._eea_mover_draft)
        self.assertTrue(stale[0]["auto_filled_only"])
        self.assertFalse(stale[0]["human_input_present"])
        self.assertTrue(stale[0]["safe_to_retract"])

    def test_a_submitted_stale_form_is_not_safe_to_retract(self):
        case = self._case(origin="FR")
        dep = self._spouse(case)
        tpl = self._fam_spouse_template(gated=True)
        self._attach(case, tpl, dependent_id=dep, submitted=True)

        stale = sfr.find_stale_case_forms(draft_loader=self._eea_mover_draft)
        self.assertTrue(stale[0]["submitted"])
        self.assertFalse(stale[0]["safe_to_retract"])

    def test_nothing_attached_returns_empty(self):
        self.assertEqual(sfr.find_stale_case_forms(draft_loader=self._eea_mover_draft), [])

    def test_country_filter_scopes_to_one_destination(self):
        de = self._case(origin="FR", dest="DE")
        dep = self._spouse(de)
        tpl = self._fam_spouse_template(gated=True)
        self._attach(de, tpl, dependent_id=dep)

        self.assertEqual(sfr.find_stale_case_forms(country="NO", draft_loader=self._eea_mover_draft), [])
        self.assertEqual(len(sfr.find_stale_case_forms(country="DE", draft_loader=self._eea_mover_draft)), 1)


if __name__ == "__main__":
    unittest.main()
