"""
Tests for [P2-1] Pre-Fill Engine.

Follows the exact same pattern as test_trigger_engine.py:
  - sys.path.insert(_REPO_ROOT) so `from backend.app.services import ...` resolves
  - SQLite in-memory DB created in setUp
  - mock.patch.object on prefill_engine.db to swap the engine per test
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

from backend.app.services import prefill_engine  # noqa: E402
from backend.app.services.prefill_engine import (  # noqa: E402
    _resolve_path,
    run_prefill,
    run_prefill_for_dependents,
)


# ---------------------------------------------------------------------------
# SQLite schema — mirrors only the tables prefill_engine reads / writes
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE cases (
    id                  TEXT PRIMARY KEY,
    employee_id         TEXT,
    dest_country_code   TEXT,
    origin_country_code TEXT,
    intake_data         TEXT DEFAULT '{}'
);
CREATE TABLE profiles (
    id        TEXT PRIMARY KEY,
    full_name TEXT,
    email     TEXT
);
CREATE TABLE form_templates (
    id     TEXT PRIMARY KEY,
    code   TEXT NOT NULL,
    fields TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE case_forms (
    id               TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    form_template_id TEXT NOT NULL,
    person_id        TEXT,
    dependent_id     TEXT,
    status           TEXT NOT NULL DEFAULT 'not_started',
    completion_pct   INTEGER NOT NULL DEFAULT 0,
    blocker_form_id  TEXT,
    updated_at       TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
    id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id  TEXT NOT NULL,
    field_id      TEXT NOT NULL,
    value         TEXT,
    filled_by     TEXT NOT NULL,
    ai_confidence REAL,
    reviewed      INTEGER NOT NULL DEFAULT 0,
    overridden    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (case_form_id, field_id)
);
CREATE TABLE case_dependents (
    id            TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL,
    relationship  TEXT NOT NULL,
    full_name     TEXT,
    date_of_birth TEXT,
    nationality   TEXT,
    passport_expiry TEXT
);
CREATE TABLE audit_logs (
    id             TEXT PRIMARY KEY,
    entity_type    TEXT NOT NULL,
    entity_id      TEXT NOT NULL,
    action_type    TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT,
    actor_type     TEXT NOT NULL DEFAULT 'system',
    actor_id       TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_case(conn, case_id, employee_id, intake_data=None,
                 dest="NO", origin="FR"):
    conn.execute(text(
        "INSERT INTO cases (id, employee_id, dest_country_code, "
        "origin_country_code, intake_data) "
        "VALUES (:id, :emp, :dest, :origin, :intake)"
    ), {"id": case_id, "emp": employee_id,
        "dest": dest, "origin": origin,
        "intake": json.dumps(intake_data or {})})


def _insert_profile(conn, profile_id, full_name="Test Employee",
                    email="test@example.com"):
    conn.execute(text(
        "INSERT INTO profiles (id, full_name, email) VALUES (:id, :n, :e)"
    ), {"id": profile_id, "n": full_name, "e": email})


def _insert_template(conn, template_id, code, fields):
    conn.execute(text(
        "INSERT INTO form_templates (id, code, fields) "
        "VALUES (:id, :code, :fields)"
    ), {"id": template_id, "code": code, "fields": json.dumps(fields)})


def _insert_case_form(conn, cf_id, case_id, template_id,
                      person_id=None, dependent_id=None):
    conn.execute(text(
        "INSERT INTO case_forms "
        "(id, case_id, form_template_id, person_id, dependent_id) "
        "VALUES (:id, :cid, :tid, :pid, :did)"
    ), {"id": cf_id, "cid": case_id, "tid": template_id,
        "pid": person_id, "did": dependent_id})


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class PreFillEngineTests(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        # Patch the module-level `db` object's engine for this test
        self.patcher = mock.patch.object(prefill_engine.db, "engine", self.engine)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()

    # ── path resolution ──────────────────────────────────────────────────────

    def test_resolve_path_simple(self):
        ctx = {"profile": {"passport_number": "AB123"}}
        self.assertEqual(_resolve_path(ctx, "profile.passport_number"), "AB123")

    def test_resolve_path_missing_key_returns_none(self):
        ctx = {"profile": {}}
        self.assertIsNone(_resolve_path(ctx, "profile.passport_number"))

    def test_resolve_path_empty_string_returns_none(self):
        ctx = {"profile": {"passport_number": "   "}}
        self.assertIsNone(_resolve_path(ctx, "profile.passport_number"))

    def test_resolve_path_nested_family(self):
        ctx = {"family": {"spouse": {"full_name": "Jane Doe"}}}
        self.assertEqual(
            _resolve_path(ctx, "family.spouse.full_name"), "Jane Doe"
        )

    def test_resolve_path_missing_segment_returns_none(self):
        ctx = {"contract": {"employer_name": "Acme"}}
        self.assertIsNone(_resolve_path(ctx, "contract.missing_key"))

    # ── happy path — fills fields from intake_data ───────────────────────────

    def test_fills_fields_from_intake_data(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [
            {"id": "passport_number", "prefill_source": "profile.passport_number"},
            {"id": "employer_name",   "prefill_source": "contract.employer_name"},
        ]
        intake = {
            "profile":  {"passport_number": "X123456"},
            "contract": {"employer_name":   "Acme Norway AS"},
        }
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        filled = run_prefill(cf_id, case_id)
        self.assertEqual(filled, 2)

        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT field_id, value, filled_by, ai_confidence "
                "FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).fetchall()

        values = {r[0]: r[1] for r in rows}
        self.assertEqual(values["passport_number"], "X123456")
        self.assertEqual(values["employer_name"],   "Acme Norway AS")
        self.assertEqual(rows[0][2], "system")
        self.assertAlmostEqual(rows[0][3], 0.99, places=2)

    # ── [P2-03d] audit logging ───────────────────────────────────────────────

    def test_prefill_writes_audit_log(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [
            {"id": "passport_number", "prefill_source": "profile.passport_number"},
            {"id": "employer_name",   "prefill_source": "contract.employer_name"},
        ]
        intake = {
            "profile":  {"passport_number": "X123456"},
            "contract": {"employer_name":   "Acme Norway AS"},
        }
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        run_prefill(cf_id, case_id)

        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT entity_type, entity_id, action_type, actor_type, "
                "       new_value_json "
                "FROM audit_logs WHERE entity_id = :id"
            ), {"id": cf_id}).fetchall()

        # Exactly one audit row per pre-fill event.
        self.assertEqual(len(rows), 1)
        entity_type, entity_id, action_type, actor_type, new_json = rows[0]
        self.assertEqual(entity_type, "case_form")
        self.assertEqual(entity_id, cf_id)
        self.assertEqual(action_type, "insert")   # CHECK-constrained value
        self.assertEqual(actor_type, "system")

        payload = json.loads(new_json)
        self.assertEqual(payload["event"], "prefill")
        self.assertEqual(payload["form_id"], cf_id)
        self.assertEqual(payload["field_count"], 2)
        self.assertEqual(
            sorted(payload["fields_filled"]),
            ["employer_name", "passport_number"],
        )

    def test_no_audit_log_when_nothing_filled(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [{"id": "salary", "prefill_source": "contract.salary_amount_nok"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "GP-7-04", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 0)

        with self.engine.connect() as conn:
            count = conn.execute(text(
                "SELECT COUNT(*) FROM audit_logs WHERE entity_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(count, 0)

    def test_rerun_with_no_changes_writes_no_new_audit(self):
        # A re-fill (e.g. run_prefill_for_dependents after a blocker is approved)
        # that resolves the same values must NOT record a second prefill event.
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [{"id": "passport_number", "prefill_source": "profile.passport_number"}]
        intake = {"profile": {"passport_number": "X1"}}
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)   # first fill changes 1
        self.assertEqual(run_prefill(cf_id, case_id), 0)   # re-run changes nothing

        with self.engine.connect() as conn:
            audit_count = conn.execute(text(
                "SELECT COUNT(*) FROM audit_logs WHERE entity_id = :id"
            ), {"id": cf_id}).scalar()
            value_count = conn.execute(text(
                "SELECT COUNT(*) FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(audit_count, 1)   # exactly one prefill event, not two
        self.assertEqual(value_count, 1)

    def test_rerun_after_value_change_audits_only_changed_field(self):
        # When a re-fill genuinely changes a value, a fresh audit row is written
        # listing only the changed field.
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [
            {"id": "passport_number", "prefill_source": "profile.passport_number"},
            {"id": "nationality",     "prefill_source": "profile.nationality"},
        ]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id,
                         {"profile": {"passport_number": "X1", "nationality": "FR"}})
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 2)

        # passport_number changes; nationality stays the same.
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE cases SET intake_data = :d WHERE id = :id"
            ), {"d": json.dumps({"profile": {"passport_number": "X2", "nationality": "FR"}}),
                "id": case_id})

        self.assertEqual(run_prefill(cf_id, case_id), 1)   # only passport_number changed

        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT new_value_json FROM audit_logs WHERE entity_id = :id"
            ), {"id": cf_id}).fetchall()
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values "
                "WHERE case_form_id = :id AND field_id = 'passport_number'"
            ), {"id": cf_id}).scalar()
        payloads = [json.loads(r[0]) for r in rows]
        self.assertEqual(len(payloads), 2)                   # two distinct events
        # Order-independent: the initial event filled 2 fields; the re-fill 1.
        self.assertCountEqual([p["field_count"] for p in payloads], [2, 1])
        change_event = next(p for p in payloads if p["field_count"] == 1)
        self.assertEqual(change_event["fields_filled"], ["passport_number"])
        self.assertEqual(val, "X2")                          # value actually updated

    def test_skips_fields_without_prefill_source(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [
            {"id": "passport_number", "prefill_source": "profile.passport_number"},
            {"id": "comments",        "prefill_source": None},
        ]
        intake = {"profile": {"passport_number": "Z999"}}
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)

    def test_skips_fields_with_unresolvable_source(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [{"id": "salary", "prefill_source": "contract.salary_amount_nok"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "GP-7-04", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 0)

    # ── idempotency ──────────────────────────────────────────────────────────

    def test_idempotent_does_not_duplicate_rows(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields  = [{"id": "passport_number", "prefill_source": "profile.passport_number"}]
        intake  = {"profile": {"passport_number": "P555"}}
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        run_prefill(cf_id, case_id)
        run_prefill(cf_id, case_id)

        with self.engine.connect() as conn:
            count = conn.execute(text(
                "SELECT count(*) FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(count, 1)

    def test_does_not_overwrite_overridden_fields(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields  = [{"id": "passport_number", "prefill_source": "profile.passport_number"}]
        intake  = {"profile": {"passport_number": "SYSTEM_VALUE"}}
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)
            # Simulate user override
            conn.execute(text(
                "INSERT INTO case_form_field_values "
                "(id, case_form_id, field_id, value, filled_by, overridden) "
                "VALUES (:id, :cfid, 'passport_number', 'USER_VALUE', 'employee', 1)"
            ), {"id": _uuid(), "cfid": cf_id})

        run_prefill(cf_id, case_id)

        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values "
                "WHERE case_form_id = :id AND field_id = 'passport_number'"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "USER_VALUE")

    # ── completion % and status ──────────────────────────────────────────────

    def test_updates_completion_pct(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields = [
            {"id": "f1", "prefill_source": "profile.passport_number"},
            {"id": "f2", "prefill_source": "profile.nationality"},
            {"id": "f3", "prefill_source": "contract.salary_amount_nok"},  # no data
        ]
        intake = {"profile": {"passport_number": "P1", "nationality": "FR"}}
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        run_prefill(cf_id, case_id)

        with self.engine.connect() as conn:
            pct = conn.execute(text(
                "SELECT completion_pct FROM case_forms WHERE id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(pct, 67)  # 2/3 = 66.6 → rounds to 67

    def test_status_set_to_auto_filled_when_fields_written(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields  = [{"id": "passport_number", "prefill_source": "profile.passport_number"}]
        intake  = {"profile": {"passport_number": "P9"}}
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        run_prefill(cf_id, case_id)

        with self.engine.connect() as conn:
            status = conn.execute(text(
                "SELECT status FROM case_forms WHERE id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(status, "auto_filled")

    def test_status_not_downgraded_if_already_advanced(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields  = [{"id": "passport_number", "prefill_source": "profile.passport_number"}]
        intake  = {"profile": {"passport_number": "P9"}}
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)
            conn.execute(text(
                "UPDATE case_forms SET status = 'submitted' WHERE id = :id"
            ), {"id": cf_id})

        run_prefill(cf_id, case_id)

        with self.engine.connect() as conn:
            status = conn.execute(text(
                "SELECT status FROM case_forms WHERE id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(status, "submitted")

    # ── camelCase intake key aliases ─────────────────────────────────────────

    def test_resolves_camelcase_intake_keys(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields  = [{"id": "employer_name", "prefill_source": "contract.employer_name"}]
        intake  = {"contract": {"employerName": "Norsk AS"}}  # camelCase
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)

        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "Norsk AS")

    def test_resolves_camelcase_profile_keys(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields  = [{"id": "dob", "prefill_source": "profile.date_of_birth"}]
        intake  = {"profile": {"dateOfBirth": "1990-01-01"}}  # camelCase
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)

    # ── dependent / family context ───────────────────────────────────────────

    def test_resolves_spouse_data(self):
        case_id = _uuid();  emp_id = _uuid();  dep_id = _uuid()
        cf_id = _uuid();    tmpl = _uuid()
        fields  = [{"id": "spouse_name", "prefill_source": "family.spouse.full_name"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            conn.execute(text(
                "INSERT INTO case_dependents "
                "(id, case_id, relationship, full_name) "
                "VALUES (:id, :cid, 'spouse', 'Jane Doe')"
            ), {"id": dep_id, "cid": case_id})
            _insert_template(conn, tmpl, "UTL-2011F", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, dependent_id=dep_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)
        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "Jane Doe")

    def test_resolves_spouse_legal_full_name_alias(self):
        """family.spouse.legal_full_name resolves via full_name alias (UTL-2011F seed path)."""
        case_id = _uuid();  emp_id = _uuid();  dep_id = _uuid()
        cf_id = _uuid();    tmpl = _uuid()
        fields = [{"id": "spouse_full_name", "prefill_source": "family.spouse.legal_full_name"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            conn.execute(text(
                "INSERT INTO case_dependents "
                "(id, case_id, relationship, full_name) "
                "VALUES (:id, :cid, 'spouse', 'Marie Curie')"
            ), {"id": dep_id, "cid": case_id})
            _insert_template(conn, tmpl, "UTL-2011F", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, dependent_id=dep_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)
        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "Marie Curie")

    def test_resolves_spouse_passport_expiry(self):
        """family.spouse.passport_expiry resolves from case_dependents row."""
        case_id = _uuid();  emp_id = _uuid();  dep_id = _uuid()
        cf_id = _uuid();    tmpl = _uuid()
        fields = [{"id": "spouse_passport_expiry", "prefill_source": "family.spouse.passport_expiry"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            conn.execute(text(
                "INSERT INTO case_dependents "
                "(id, case_id, relationship, full_name, passport_expiry) "
                "VALUES (:id, :cid, 'spouse', 'Jane Doe', '2030-06-15')"
            ), {"id": dep_id, "cid": case_id})
            _insert_template(conn, tmpl, "UTL-2011F", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, dependent_id=dep_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)
        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "2030-06-15")

    def test_resolves_person_legal_full_name_alias(self):
        """person.legal_full_name resolves via full_name alias (UTL-2011B child seed path)."""
        case_id = _uuid();  emp_id = _uuid();  dep_id = _uuid()
        cf_id = _uuid();    tmpl = _uuid()
        fields = [{"id": "child_full_name", "prefill_source": "person.legal_full_name"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            conn.execute(text(
                "INSERT INTO case_dependents "
                "(id, case_id, relationship, full_name) "
                "VALUES (:id, :cid, 'child', 'Tim Doe')"
            ), {"id": dep_id, "cid": case_id})
            _insert_template(conn, tmpl, "UTL-2011B", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, dependent_id=dep_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)
        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "Tim Doe")

    def test_resolves_person_relationship(self):
        """person.relationship resolves from case_dependents.relationship (UTL-2011B seed path)."""
        case_id = _uuid();  emp_id = _uuid();  dep_id = _uuid()
        cf_id = _uuid();    tmpl = _uuid()
        fields = [{"id": "relationship_to_employee", "prefill_source": "person.relationship"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            conn.execute(text(
                "INSERT INTO case_dependents "
                "(id, case_id, relationship, full_name) "
                "VALUES (:id, :cid, 'child', 'Tim Doe')"
            ), {"id": dep_id, "cid": case_id})
            _insert_template(conn, tmpl, "UTL-2011B", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, dependent_id=dep_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)
        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "child")

    def test_resolves_person_passport_expiry(self):
        """person.passport_expiry resolves from case_dependents.passport_expiry (UTL-2011B path)."""
        case_id = _uuid();  emp_id = _uuid();  dep_id = _uuid()
        cf_id = _uuid();    tmpl = _uuid()
        fields = [{"id": "child_passport_expiry", "prefill_source": "person.passport_expiry"}]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            conn.execute(text(
                "INSERT INTO case_dependents "
                "(id, case_id, relationship, full_name, passport_expiry) "
                "VALUES (:id, :cid, 'child', 'Tim Doe', '2028-03-01')"
            ), {"id": dep_id, "cid": case_id})
            _insert_template(conn, tmpl, "UTL-2011B", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, dependent_id=dep_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)
        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "2028-03-01")

    def test_falls_back_to_profiles_full_name_for_legal_name(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        fields  = [{"id": "full_name", "prefill_source": "profile.legal_full_name"}]
        # No intake_data profile key, but profiles.full_name exists
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id, full_name="Alice Dupont")
            _insert_template(conn, tmpl, "UTL-2011", fields)
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 1)
        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(val, "Alice Dupont")

    # ── edge cases ───────────────────────────────────────────────────────────

    def test_missing_case_form_is_noop(self):
        self.assertEqual(run_prefill("non-existent-id", "non-existent-case"), 0)

    def test_empty_fields_array_is_noop(self):
        case_id = _uuid();  emp_id = _uuid();  cf_id = _uuid();  tmpl = _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, {})
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl, "EMPTY", [])
            _insert_case_form(conn, cf_id, case_id, tmpl, person_id=emp_id)

        self.assertEqual(run_prefill(cf_id, case_id), 0)

    def test_error_does_not_raise(self):
        # Totally invalid IDs — must return 0, not raise
        self.assertEqual(run_prefill("", ""), 0)

    # ── dependency re-fill ───────────────────────────────────────────────────

    def test_run_prefill_for_dependents_fills_blocked_forms(self):
        case_id    = _uuid();  emp_id = _uuid()
        blocker_id = _uuid();  blocked_id = _uuid()
        tmpl_a = _uuid();      tmpl_b = _uuid()
        fields = [{"id": "passport_number", "prefill_source": "profile.passport_number"}]
        intake = {"profile": {"passport_number": "X111"}}

        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id, intake)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl_a, "GP-7-04", fields)
            _insert_template(conn, tmpl_b, "HELFO-1", fields)
            _insert_case_form(conn, blocker_id, case_id, tmpl_a, person_id=emp_id)
            _insert_case_form(conn, blocked_id, case_id, tmpl_b, person_id=emp_id)
            conn.execute(text(
                "UPDATE case_forms SET blocker_form_id = :bid WHERE id = :id"
            ), {"bid": blocker_id, "id": blocked_id})

        total = run_prefill_for_dependents(blocker_id, case_id)
        self.assertEqual(total, 1)

        with self.engine.connect() as conn:
            val = conn.execute(text(
                "SELECT value FROM case_form_field_values WHERE case_form_id = :id"
            ), {"id": blocked_id}).scalar()
        self.assertEqual(val, "X111")


if __name__ == "__main__":
    unittest.main()
