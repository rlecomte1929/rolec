"""
Tests for backend/app/services/trigger_engine.py.

Mirrors the pattern from test_admin_form_templates_router.py: swap `db.engine`
for an in-memory SQLite engine with a schema that mirrors the production
public.cases / case_dependents / form_templates / case_forms / case_events
tables, then exercise the engine's public + helper functions directly.

Portability note:
  Postgres ships with UNIQUE NULLS NOT DISTINCT (15+); SQLite doesn't.
  For idempotency tests, the SQLite schema replicates the constraint
  semantics using COALESCE in a unique index (CONFLICT routing via a
  computed expression).
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

from backend.app.services import trigger_engine as engine_module  # noqa: E402
from backend.app.services.trigger_engine import (  # noqa: E402
    _derive_events,
    _matches_conditions,
    _purpose_to_visa_type,
    _resolve_persons,
    _to_uuid,
    fire_roadmap_events,
)


# SQLite schema mirroring just the tables trigger_engine reads/writes.
# - jsonb columns become TEXT (we json.dumps on insert / json.loads on read).
# - The UNIQUE NULLS NOT DISTINCT constraint is emulated by a unique index
#   over COALESCE(person_id, '_'), COALESCE(dependent_id, '_').
SCHEMA = """
CREATE TABLE cases (
  id                 TEXT PRIMARY KEY,
  employee_id        TEXT,
  dest_country_code  TEXT,
  purpose            TEXT
);
CREATE TABLE case_dependents (
  id            TEXT PRIMARY KEY,
  case_id       TEXT NOT NULL,
  relationship  TEXT NOT NULL,
  full_name     TEXT
);
CREATE TABLE form_templates (
  id             TEXT PRIMARY KEY,
  code           TEXT NOT NULL,
  trigger_rules  TEXT NOT NULL DEFAULT '[]',
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE case_forms (
  id                TEXT PRIMARY KEY,
  case_id           TEXT NOT NULL,
  form_template_id  TEXT NOT NULL,
  person_id         TEXT,
  dependent_id      TEXT,
  status            TEXT NOT NULL DEFAULT 'not_started',
  blocker_form_id   TEXT
);
CREATE UNIQUE INDEX case_forms_unique_person_dep
  ON case_forms (
    case_id,
    form_template_id,
    COALESCE(person_id, '__null__'),
    COALESCE(dependent_id, '__null__')
  );
CREATE TABLE case_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id     TEXT NOT NULL,
  event_type  TEXT NOT NULL,
  description TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


class TriggerEngineHelperTests(unittest.TestCase):
    """Pure-function helpers — no DB needed."""

    def test_to_uuid_valid(self) -> None:
        u = _uuid()
        self.assertEqual(_to_uuid(u), u)

    def test_to_uuid_invalid(self) -> None:
        self.assertIsNone(_to_uuid("not-a-uuid"))
        self.assertIsNone(_to_uuid(""))
        self.assertIsNone(_to_uuid(None))

    def test_purpose_to_visa_type(self) -> None:
        self.assertEqual(_purpose_to_visa_type("work"), "skilled_worker")
        self.assertEqual(_purpose_to_visa_type("intra_company_transfer"), "intra_company_transfer")
        self.assertEqual(_purpose_to_visa_type("family_join"), "family_join")
        self.assertEqual(_purpose_to_visa_type("remote_work"), "remote_work")
        self.assertIsNone(_purpose_to_visa_type("unknown"))

    def test_matches_conditions_all_must_match(self) -> None:
        ctx = {"destination_country": "NO", "visa_type": "skilled_worker", "has_spouse": False}
        self.assertTrue(_matches_conditions({"destination_country": "NO"}, ctx))
        self.assertTrue(_matches_conditions(
            {"destination_country": "NO", "visa_type": "skilled_worker"}, ctx
        ))
        self.assertFalse(_matches_conditions({"destination_country": "FR"}, ctx))
        self.assertFalse(_matches_conditions(
            {"destination_country": "NO", "visa_type": "blue_card"}, ctx
        ))

    def test_matches_conditions_handles_bool(self) -> None:
        ctx = {"has_spouse": True, "has_children": False}
        self.assertTrue(_matches_conditions({"has_spouse": True}, ctx))
        self.assertFalse(_matches_conditions({"has_spouse": False}, ctx))
        self.assertFalse(_matches_conditions({"has_children": True}, ctx))

    def test_matches_conditions_missing_key_fails(self) -> None:
        self.assertFalse(_matches_conditions({"destination_country": "NO"}, {}))

    def test_resolve_persons_employee(self) -> None:
        out = _resolve_persons(["employee"], "emp-1", [])
        self.assertEqual(out, [("emp-1", None)])

    def test_resolve_persons_spouse(self) -> None:
        deps = [
            {"id": "dep-1", "relationship": "spouse"},
            {"id": "dep-2", "relationship": "child"},
        ]
        out = _resolve_persons(["spouse"], "emp-1", deps)
        self.assertEqual(out, [(None, "dep-1")])

    def test_resolve_persons_each_child_produces_one_per_child(self) -> None:
        deps = [
            {"id": "dep-1", "relationship": "spouse"},
            {"id": "dep-2", "relationship": "child"},
            {"id": "dep-3", "relationship": "child"},
            {"id": "dep-4", "relationship": "child"},
        ]
        out = _resolve_persons(["each_child"], "emp-1", deps)
        self.assertEqual(set(out), {(None, "dep-2"), (None, "dep-3"), (None, "dep-4")})
        self.assertEqual(len(out), 3)

    def test_resolve_persons_unknown_tag_falls_back_to_employee(self) -> None:
        out = _resolve_persons(["weird_tag"], "emp-1", [])
        self.assertEqual(out, [("emp-1", None)])

    def test_derive_events_destination_only(self) -> None:
        ctx = {"destination_country": "NO"}
        events = _derive_events(ctx, draft={}, derived={})
        self.assertIn("roadmap.destination_confirmed", events)
        self.assertNotIn("roadmap.profile_completed", events)

    def test_derive_events_with_origin_adds_profile_completed(self) -> None:
        ctx = {"destination_country": "NO"}
        events = _derive_events(
            ctx,
            draft={"relocationBasics": {"originCountry": "FR"}},
            derived={},
        )
        self.assertIn("roadmap.profile_completed", events)

    def test_derive_events_arrival_confirmed(self) -> None:
        ctx = {"destination_country": "NO"}
        events = _derive_events(ctx, draft={"arrival": {"confirmed": True}}, derived={})
        self.assertIn("roadmap.arrival_confirmed", events)

    def test_derive_events_contract_details_saved(self) -> None:
        ctx = {"destination_country": "NO"}
        events = _derive_events(
            ctx, draft={"contract": {"employerName": "Equinor"}}, derived={}
        )
        self.assertIn("roadmap.contract_details_saved", events)


class TriggerEngineIntegrationTests(unittest.TestCase):
    """Full fire_roadmap_events flow against the SQLite test schema."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.engine_patcher = mock.patch.object(engine_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

        # Seed a baseline case + the relevant Norway templates
        self.case_id = _uuid()
        self.employee_id = _uuid()
        self._insert_case(
            case_id=self.case_id,
            employee_id=self.employee_id,
            dest_country_code="NO",
            purpose="work",
        )
        self._insert_template(
            code="UTL-2011",
            rules=[{
                "event": "roadmap.destination_confirmed",
                "conditions": {"destination_country": "NO", "visa_type": "skilled_worker"},
                "for_persons": ["employee"],
                "blocked_by_template_code": None,
            }],
        )
        self._insert_template(
            code="UTL-2011F",
            rules=[{
                "event": "roadmap.profile_completed",
                "conditions": {"destination_country": "NO", "has_spouse": True},
                "for_persons": ["spouse"],
                "blocked_by_template_code": None,
            }],
        )
        self._insert_template(
            code="UTL-2011B",
            rules=[{
                "event": "roadmap.profile_completed",
                "conditions": {"destination_country": "NO", "has_children": True},
                "for_persons": ["each_child"],
                "blocked_by_template_code": None,
            }],
        )
        self._insert_template(
            code="GP-7-04",
            rules=[{
                "event": "roadmap.destination_confirmed",
                "conditions": {"destination_country": "NO"},
                "for_persons": ["employee"],
                "blocked_by_template_code": None,
            }],
        )
        self._insert_template(
            code="HELFO-1",
            rules=[{
                "event": "roadmap.arrival_confirmed",
                "conditions": {"destination_country": "NO"},
                "for_persons": ["employee"],
                "blocked_by_template_code": "GP-7-04",
            }],
        )

    # ── helpers ────────────────────────────────────────────────────────────
    def _insert_case(self, *, case_id: str, employee_id: str,
                     dest_country_code: str, purpose: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id, employee_id, dest_country_code, purpose) "
                     "VALUES (:id, :eid, :dest, :purpose)"),
                {"id": case_id, "eid": employee_id, "dest": dest_country_code, "purpose": purpose},
            )

    def _insert_template(self, *, code: str, rules: list) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO form_templates (id, code, trigger_rules) "
                     "VALUES (:id, :code, :rules)"),
                {"id": _uuid(), "code": code, "rules": json.dumps(rules)},
            )

    def _insert_dependent(self, *, case_id: str, relationship: str,
                          full_name: str = "") -> str:
        dep_id = _uuid()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_dependents (id, case_id, relationship, full_name) "
                     "VALUES (:id, :cid, :rel, :name)"),
                {"id": dep_id, "cid": case_id, "rel": relationship, "name": full_name},
            )
        return dep_id

    def _case_forms(self) -> list:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT cf.code, cf.case_id, cf.person_id, cf.dependent_id, cf.blocker_form_id "
                "FROM ("
                "  SELECT case_forms.id, ft.code, case_forms.case_id, case_forms.person_id, "
                "         case_forms.dependent_id, case_forms.blocker_form_id "
                "  FROM case_forms JOIN form_templates ft ON ft.id = case_forms.form_template_id"
                ") cf"
            )).mappings().all()
        return [dict(r) for r in rows]

    def _events(self) -> list:
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(
                "SELECT event_type, description FROM case_events ORDER BY id"
            )).mappings().all()]

    # ── tests ──────────────────────────────────────────────────────────────
    def test_invalid_case_id_is_noop(self) -> None:
        n = fire_roadmap_events(case_id="not-a-uuid", draft={}, derived={})
        self.assertEqual(n, 0)
        self.assertEqual(self._case_forms(), [])

    def test_missing_case_row_is_noop(self) -> None:
        n = fire_roadmap_events(
            case_id=_uuid(),
            draft={"relocationBasics": {"destCountry": "NO"}},
            derived={"dest_country": "NO"},
        )
        self.assertEqual(n, 0)

    def test_no_dest_no_events_no_forms(self) -> None:
        # Wipe destination from the case
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE cases SET dest_country_code = NULL WHERE id = :id"),
                         {"id": self.case_id})
        n = fire_roadmap_events(case_id=self.case_id, draft={}, derived={})
        self.assertEqual(n, 0)

    def test_destination_confirmed_creates_utl2011_for_employee(self) -> None:
        n = fire_roadmap_events(
            case_id=self.case_id,
            draft={},
            derived={"dest_country": "NO"},
        )
        # UTL-2011 (employee, skilled_worker) + GP-7-04 (employee, dest=NO)
        self.assertEqual(n, 2)
        codes = sorted(cf["code"] for cf in self._case_forms())
        self.assertEqual(codes, ["GP-7-04", "UTL-2011"])
        # Employee form has person_id set, dependent_id null
        utl = next(cf for cf in self._case_forms() if cf["code"] == "UTL-2011")
        self.assertEqual(utl["person_id"], self.employee_id)
        self.assertIsNone(utl["dependent_id"])

    def test_re_firing_same_event_is_idempotent(self) -> None:
        fire_roadmap_events(case_id=self.case_id, draft={}, derived={"dest_country": "NO"})
        n_second = fire_roadmap_events(
            case_id=self.case_id, draft={}, derived={"dest_country": "NO"}
        )
        self.assertEqual(n_second, 0)
        codes = sorted(cf["code"] for cf in self._case_forms())
        self.assertEqual(codes, ["GP-7-04", "UTL-2011"])

    def test_has_spouse_creates_utl2011f(self) -> None:
        spouse_id = self._insert_dependent(case_id=self.case_id, relationship="spouse")
        n = fire_roadmap_events(
            case_id=self.case_id,
            draft={"relocationBasics": {"originCountry": "FR"}},
            derived={"dest_country": "NO"},
        )
        # Expected: UTL-2011 + GP-7-04 (destination_confirmed)
        #         + UTL-2011F (profile_completed, has_spouse=true)
        codes = sorted(cf["code"] for cf in self._case_forms())
        self.assertEqual(codes, ["GP-7-04", "UTL-2011", "UTL-2011F"])
        self.assertEqual(n, 3)
        utl_f = next(cf for cf in self._case_forms() if cf["code"] == "UTL-2011F")
        self.assertIsNone(utl_f["person_id"])
        self.assertEqual(utl_f["dependent_id"], spouse_id)

    def test_each_child_creates_one_form_per_child(self) -> None:
        c1 = self._insert_dependent(case_id=self.case_id, relationship="child")
        c2 = self._insert_dependent(case_id=self.case_id, relationship="child")
        fire_roadmap_events(
            case_id=self.case_id,
            draft={"relocationBasics": {"originCountry": "FR"}},
            derived={"dest_country": "NO"},
        )
        utl_b_forms = [cf for cf in self._case_forms() if cf["code"] == "UTL-2011B"]
        self.assertEqual(len(utl_b_forms), 2)
        dep_ids = sorted(cf["dependent_id"] for cf in utl_b_forms)
        self.assertEqual(dep_ids, sorted([c1, c2]))

    def test_arrival_confirmed_creates_helfo1_and_resolves_blocker(self) -> None:
        # Fire destination first so GP-7-04 exists to serve as a blocker
        fire_roadmap_events(case_id=self.case_id, draft={}, derived={"dest_country": "NO"})
        # Now fire arrival
        n = fire_roadmap_events(
            case_id=self.case_id,
            draft={"arrival": {"confirmed": True}},
            derived={"dest_country": "NO"},
        )
        self.assertEqual(n, 1)
        helfo = next(cf for cf in self._case_forms() if cf["code"] == "HELFO-1")
        self.assertIsNotNone(helfo["blocker_form_id"])
        # Resolved correctly to the GP-7-04 case_form
        gp = next(cf for cf in self._case_forms() if cf["code"] == "GP-7-04")
        with self.engine.connect() as conn:
            gp_id = conn.execute(text(
                "SELECT case_forms.id FROM case_forms "
                "JOIN form_templates ft ON ft.id = case_forms.form_template_id "
                "WHERE ft.code = 'GP-7-04'"
            )).scalar()
        self.assertEqual(helfo["blocker_form_id"], gp_id)

    def test_case_form_created_events_emitted(self) -> None:
        fire_roadmap_events(case_id=self.case_id, draft={}, derived={"dest_country": "NO"})
        events = self._events()
        # One case_events row per CaseForm created (UTL-2011 + GP-7-04 = 2)
        self.assertEqual(len(events), 2)
        self.assertTrue(all(e["event_type"] == "case_form.created" for e in events))
        # Descriptions reference template code + fired event
        descriptions = " ".join(e["description"] for e in events)
        self.assertIn("UTL-2011", descriptions)
        self.assertIn("GP-7-04", descriptions)
        self.assertIn("roadmap.destination_confirmed", descriptions)

    def test_error_in_engine_does_not_raise(self) -> None:
        # Drop the form_templates table to force an error mid-flight
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE form_templates"))
        # Must not raise — engine swallows + logs
        result = fire_roadmap_events(
            case_id=self.case_id, draft={}, derived={"dest_country": "NO"}
        )
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
