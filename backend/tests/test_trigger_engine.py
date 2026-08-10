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


# [AIQ-1795] The post-fix RESID-PERMIT-DE conditions — one rule per NON-EEA visa_type, because
# _matches_conditions compares scalars and has no list support. Must stay in step with both
# _purpose_to_visa_type and the migration; TriggerRuleVocabularyDriftTests enforces that.
_RESID_PERMIT_DE_GATED_CONDITIONS = [
    {"destination_country": "DE", "visa_type": "skilled_worker"},
    {"destination_country": "DE", "visa_type": "intra_company_transfer"},
    {"destination_country": "DE", "visa_type": "family_join"},
    {"destination_country": "DE", "visa_type": "remote_work"},
]

_RESID_PERMIT_MIGRATION = os.path.join(
    _REPO_ROOT, "supabase", "migrations",
    "20261023000000_resid_permit_de_gate_non_eea.sql",
)


# SQLite schema mirroring just the tables trigger_engine reads/writes.
# - jsonb columns become TEXT (we json.dumps on insert / json.loads on read).
# - The UNIQUE NULLS NOT DISTINCT constraint is emulated by a unique index
#   over COALESCE(person_id, '_'), COALESCE(dependent_id, '_').
SCHEMA = """
CREATE TABLE cases (
  id                  TEXT PRIMARY KEY,
  employee_id         TEXT,
  origin_country_code TEXT,
  dest_country_code   TEXT,
  purpose             TEXT
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
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  source_language TEXT NOT NULL DEFAULT 'en'
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
        # ctx carries origin_country because _build_context always resolves it
        # (derived → draft basics → cases.origin_country_code) before calling
        # this. A ctx without it, paired with a draft that has originCountry,
        # is not a state the real caller can produce.
        ctx = {"destination_country": "NO", "origin_country": "FR"}
        events = _derive_events(
            ctx,
            draft={"relocationBasics": {"originCountry": "FR"}},
            derived={},
        )
        self.assertIn("roadmap.profile_completed", events)

    def test_derive_events_origin_comes_from_context_not_the_draft(self) -> None:
        """profile_completed must fire when only the context knows the origin."""
        ctx = {"destination_country": "NO", "origin_country": "FR"}
        events = _derive_events(ctx, draft={}, derived={})
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


class TriggerRuleVocabularyDriftTests(unittest.TestCase):
    """[AIQ-1795] Nothing but these tests stops the gate rotting.

    Gating RESID-PERMIT-DE on an enumerated list of visa_types trades one silent failure for a
    quieter one: add a fifth purpose to _purpose_to_visa_type and the template simply stops
    covering it, with no error anywhere. These pin the three places the list appears — the
    engine, the test constant, and the shipped migration — to each other.
    """

    def _non_eea_visa_types(self) -> set:
        """Every visa_type an EEA→EEA case can never produce, i.e. everything
        _purpose_to_visa_type can return. Derived from the engine, not restated."""
        purposes = ("work", "intra_company_transfer", "family_join", "remote_work")
        return {_purpose_to_visa_type(p) for p in purposes} - {None}

    def test_the_gated_conditions_cover_every_purpose_the_engine_can_map(self):
        gated = {c["visa_type"] for c in _RESID_PERMIT_DE_GATED_CONDITIONS}
        missing = sorted(self._non_eea_visa_types() - gated)
        self.assertEqual(
            missing, [],
            f"_purpose_to_visa_type can produce {missing}, which RESID-PERMIT-DE's rules do not "
            f"cover — a third-country national with that purpose would silently lose the "
            f"eAT-collection step. Add a rule to the migration and to "
            f"_RESID_PERMIT_DE_GATED_CONDITIONS.",
        )

    def test_the_gated_conditions_claim_nothing_the_engine_cannot_produce(self):
        """The reverse: a rule for a visa_type the engine never emits is dead weight that
        reads as coverage."""
        gated = {c["visa_type"] for c in _RESID_PERMIT_DE_GATED_CONDITIONS}
        unreachable = sorted(gated - self._non_eea_visa_types())
        self.assertEqual(unreachable, [], f"unreachable visa_type rules: {unreachable}")

    def test_never_gated_on_eea_registration(self):
        """The whole point. eea_registration is what _build_context emits for FR→DE."""
        gated = {c["visa_type"] for c in _RESID_PERMIT_DE_GATED_CONDITIONS}
        self.assertNotIn("eea_registration", gated)

    def test_every_condition_key_is_in_the_build_context_vocabulary(self):
        """_matches_conditions fails closed on an unknown key, so a typo would make the
        template unattachable for EVERYONE rather than erroring."""
        allowed = {
            "case_uuid", "employee_id", "destination_country", "origin_country",
            "visa_type", "has_spouse", "has_children",
        }
        for c in _RESID_PERMIT_DE_GATED_CONDITIONS:
            self.assertEqual(set(c) - allowed, set(), f"unknown condition key in {c}")

    def test_the_shipped_migration_matches_this_constant(self):
        """The constant and the migration are two hand-written copies of one list. If they
        drift, the tests pass while production behaves differently."""
        if not os.path.exists(_RESID_PERMIT_MIGRATION):
            self.skipTest("migration not present in this checkout")
        sql = open(_RESID_PERMIT_MIGRATION, encoding="utf-8").read()
        import re
        in_sql = set(re.findall(r"'visa_type',\s*'(\w+)'", sql))
        expected = {c["visa_type"] for c in _RESID_PERMIT_DE_GATED_CONDITIONS}
        self.assertEqual(
            in_sql, expected,
            f"migration declares {sorted(in_sql)}, test constant has {sorted(expected)}",
        )

    def test_the_migration_does_not_touch_the_templates_that_are_already_correct(self):
        """BLUE-CARD and WORK-VISA-DE are correctly gated; ANMELDUNG is correctly ungated.
        A migration that 'tidied' them would break real coverage."""
        if not os.path.exists(_RESID_PERMIT_MIGRATION):
            self.skipTest("migration not present in this checkout")
        sql = open(_RESID_PERMIT_MIGRATION, encoding="utf-8").read()
        # Named in comments is fine; being the target of a write is not.
        writes = sql.split("UPDATE public.form_templates", 1)[-1]
        for code in ("ANMELDUNG", "BLUE-CARD", "WORK-VISA-DE"):
            self.assertNotIn(
                f"'{code}'", writes,
                f"{code} appears in the migration's write body — it must not be modified",
            )


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
                     dest_country_code: str, purpose: str,
                     origin_country_code: str = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases "
                     "(id, employee_id, origin_country_code, dest_country_code, purpose) "
                     "VALUES (:id, :eid, :origin, :dest, :purpose)"),
                {"id": case_id, "eid": employee_id, "origin": origin_country_code,
                 "dest": dest_country_code, "purpose": purpose},
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
    def test_origin_country_falls_back_to_the_db_column(self) -> None:
        """
        A case at rest — no wizard PATCH in flight, no intake_data — must still
        resolve origin_country from cases.origin_country_code.

        Regression guard: _build_context selected dest_country_code but not
        origin_country_code, so origin_country came only from the transient
        in-flight draft. For every persisted case it was therefore None, which
        also collapsed visa_type to _purpose_to_visa_type('work') =
        'skilled_worker'. Any rule gated on origin_country or on
        visa_type=eea_registration could never fire outside a live wizard
        session. Measured in production 2026-08-04: 70 FR-NO cases, 0 attached.
        """
        fr_case = _uuid()
        self._insert_case(
            case_id=fr_case,
            employee_id=_uuid(),
            origin_country_code="FR",
            dest_country_code="NO",
            purpose="work",
        )
        self._insert_template(
            code="RP-NO-DATASHEET",
            rules=[{
                "event": "roadmap.destination_confirmed",
                "conditions": {
                    "origin_country": "FR",
                    "destination_country": "NO",
                    "visa_type": "eea_registration",
                },
                "for_persons": ["employee"],
                "blocked_by_template_code": None,
            }],
        )

        # Empty draft and empty derived == the state of every persisted case.
        fire_roadmap_events(case_id=fr_case, draft={}, derived={})

        codes = [f["code"] for f in self._case_forms() if f["case_id"] == fr_case]
        self.assertIn("RP-NO-DATASHEET", codes)

    def test_profile_completed_fires_on_a_patch_that_omits_relocation_basics(self) -> None:
        """
        The wizard does not persist relocationBasics into cases.intake_data, so a
        *second* PATCH (a later wizard step, an HR edit) arrives with a draft that
        carries no originCountry. After the _build_context fix, context resolves
        origin from cases.origin_country_code — but _derive_events recomputed it
        from derived/basics and saw an empty string.

        Result: on that second PATCH, roadmap.destination_confirmed fires (dest
        comes from the DB) while roadmap.profile_completed does not. A dependent
        added between the two PATCHes never gets its form.

        This is the narrow, real defect. Note the broader claim — that
        profile_completed never fires for a case at rest — is FALSE: measured in
        production 2026-08-04, 141 at-rest cases have a spouse and 139 already
        carry the spouse form, because the first PATCH does carry the basics.
        """
        self._insert_dependent(case_id=self.case_id, relationship="spouse",
                               full_name="Spouse Example")
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE cases SET origin_country_code = 'FR' WHERE id = :id"),
                {"id": self.case_id},
            )

        # A later PATCH: no relocationBasics in the draft, nothing in derived.
        fire_roadmap_events(case_id=self.case_id, draft={}, derived={})

        codes = [f["code"] for f in self._case_forms()]
        self.assertIn("UTL-2011F", codes)

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
            # Non-EEA origin → skilled_worker pathway (UTL-2011). (An EEA origin
            # like FR would instead select the eea_registration pathway — see
            # test_eea_origin_to_norway_triggers_eea_pathway.)
            draft={"relocationBasics": {"originCountry": "IN"}},
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

    def test_eea_origin_to_norway_triggers_eea_pathway(self) -> None:
        # [P1-04] French (EEA) national → Norway (EEA): registration scheme +
        # apostille fire on destination_confirmed; the skilled-worker permit
        # (UTL-2011, visa_type=skilled_worker) must NOT fire.
        self._insert_template(
            code="POL-EEA-REG",
            rules=[{
                "event": "roadmap.destination_confirmed",
                "conditions": {"destination_country": "NO", "visa_type": "eea_registration"},
                "for_persons": ["employee"],
                "blocked_by_template_code": None,
            }],
        )
        self._insert_template(
            code="APOSTILLE-FR",
            rules=[{
                "event": "roadmap.destination_confirmed",
                "conditions": {"destination_country": "NO", "visa_type": "eea_registration"},
                "for_persons": ["employee"],
                "blocked_by_template_code": None,
            }],
        )
        fire_roadmap_events(
            case_id=self.case_id,
            draft={"relocationBasics": {"originCountry": "FR"}},
            derived={"dest_country": "NO"},
        )
        codes = sorted(cf["code"] for cf in self._case_forms())
        # GP-7-04 (dest=NO, no visa_type) + the two EEA-pathway forms.
        self.assertEqual(codes, ["APOSTILLE-FR", "GP-7-04", "POL-EEA-REG"])
        self.assertNotIn("UTL-2011", codes)

    # ── [AIQ-1795] Germany: an EEA free-mover must not be sent for a residence permit ──
    #
    # The rule shapes below are the ones PROD actually carries, copied from
    # supabase/migrations/20260610010000_seed_de_form_templates.sql and re-verified against
    # public.form_templates on 2026-08-10. They are inlined rather than imported so the test
    # states the contract it is defending, and fails if the migration changes them.

    _DE_ARRIVAL_TEMPLATES = {
        # Correct as-is: § 17 BMG applies to everyone moving into a German dwelling, so this
        # one SHOULD be ungated. It is the control in these tests.
        "ANMELDUNG": {"destination_country": "DE"},
        # The defect: no visa_type key, so _matches_conditions never checks one and the rule
        # matches every DE-destination case — including EEA free-movers, who per
        # FreizügG/EU § 2(4) "shall not require ... a residence title in order to stay in the
        # federal territory". There is no such document for them to collect.
        "RESID-PERMIT-DE": {"destination_country": "DE"},
    }

    def _seed_de_arrival_templates(self, *, resid_permit_conditions=None) -> None:
        """Insert the two DE arrival templates. Pass a list of condition dicts to model the
        post-fix RESID-PERMIT-DE, which carries one rule per non-EEA visa_type."""
        self._insert_template(code="ANMELDUNG", rules=[{
            "event": "roadmap.arrival_confirmed",
            "conditions": self._DE_ARRIVAL_TEMPLATES["ANMELDUNG"],
            "for_persons": ["employee"],
            "blocked_by_template_code": None,
        }])
        conds = resid_permit_conditions or [self._DE_ARRIVAL_TEMPLATES["RESID-PERMIT-DE"]]
        self._insert_template(code="RESID-PERMIT-DE", rules=[
            {
                "event": "roadmap.arrival_confirmed",
                "conditions": c,
                "for_persons": ["employee"],
                "blocked_by_template_code": None,
            }
            for c in conds
        ])

    def _fire_de_arrival(self, *, origin: str, purpose: str = "work") -> list:
        case_id = _uuid()
        self._insert_case(
            case_id=case_id, employee_id=_uuid(),
            dest_country_code="DE", purpose=purpose, origin_country_code=origin,
        )
        fire_roadmap_events(
            case_id=case_id,
            draft={"arrival": {"confirmed": True}},
            derived={"dest_country": "DE", "origin_country": origin},
        )
        return sorted(
            cf["code"] for cf in self._case_forms() if cf["case_id"] == case_id
        )

    def test_an_ungated_permit_rule_attaches_on_an_eea_corridor_which_is_the_defect(self) -> None:
        """The defect, pinned as a positive assertion so it stays green.

        Seeded with the PRE-fix rule — conditions {"destination_country": "DE"} and no
        visa_type — RESID-PERMIT-DE attaches to an FR→DE case. FR→DE is EEA→EEA, so
        _build_context resolves visa_type 'eea_registration', and German law issues no
        residence title to such a person (FreizügG/EU § 2(4)). Its 5 fields are a full
        Ausländerbehörde package — passport original, biometric photo, Anmeldung reference —
        so attaching it tells an EU citizen to collect a document that does not exist.

        Paired with test_the_gated_rules_close_the_eea_hole_they_were_written_for: this one
        shows the old shape matching, that one shows the new shape not matching. Together they
        prove the trigger_rules change is what alters the behaviour, and neither has to sit red
        in CI waiting on a production apply.
        """
        self._seed_de_arrival_templates()   # pre-fix: ungated
        codes = self._fire_de_arrival(origin="FR")
        self.assertIn(
            "RESID-PERMIT-DE", codes,
            "if this stops attaching, the omitted-visa_type over-match is gone by some other "
            "route — check whether 20261023000000 is still the mechanism",
        )

    def test_anmeldung_still_attaches_on_an_eea_corridor(self) -> None:
        """The control: gating the wrong template would silently drop the one real German
        arrival obligation. § 17 BMG applies regardless of nationality."""
        self._seed_de_arrival_templates()
        codes = self._fire_de_arrival(origin="FR")
        self.assertIn("ANMELDUNG", codes)

    def test_resid_permit_de_still_attaches_for_a_non_eea_origin(self) -> None:
        """No silent coverage loss. For a third-country national the eAT-collection
        appointment is a real obligation, and this is the only template covering it — so the
        fix must gate, not delete. IN→DE resolves visa_type 'skilled_worker'.
        """
        self._seed_de_arrival_templates(
            resid_permit_conditions=_RESID_PERMIT_DE_GATED_CONDITIONS
        )
        codes = self._fire_de_arrival(origin="IN", purpose="work")
        self.assertIn("RESID-PERMIT-DE", codes)

    def test_the_gated_rules_close_the_eea_hole_they_were_written_for(self) -> None:
        """The post-fix shape, against the corridor that exposed the bug."""
        self._seed_de_arrival_templates(
            resid_permit_conditions=_RESID_PERMIT_DE_GATED_CONDITIONS
        )
        codes = self._fire_de_arrival(origin="FR")
        self.assertNotIn("RESID-PERMIT-DE", codes)
        self.assertIn("ANMELDUNG", codes)   # and did not over-correct

    def test_an_unknown_purpose_fails_closed(self) -> None:
        """visa_type is None when the purpose is unrecognised, and _matches_conditions
        returns False on a None actual — so the gated template stays shut rather than
        defaulting open."""
        self._seed_de_arrival_templates(
            resid_permit_conditions=_RESID_PERMIT_DE_GATED_CONDITIONS
        )
        codes = self._fire_de_arrival(origin="IN", purpose="sabbatical")
        self.assertNotIn("RESID-PERMIT-DE", codes)

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
