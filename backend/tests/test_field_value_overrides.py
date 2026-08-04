"""
[P4-6] Tests for field_value_overrides capture and the admin accuracy report.

Strategy:
  - SQLite in-memory DB (same approach as test_field_value_api.py)
  - Stub backend.app.db + heavy service modules at module level before importing
    the routers — avoids psycopg2 import errors in the sandbox.
  - Use mock.patch.object on main_db / db inside setUp to swap the engine.

Tests cover:
  - Override record captured when an AI-filled field is replaced
  - No override when a new field with no prior AI value is written
  - overridden_by = 'specialist' for HR / admin users
  - Accuracy report: override_rate_pct and accuracy_flag are correct
  - Validation criterion: 5 overrides of 'previous_address' in UTL-2011
    → override_rate=100%, flag='low_accuracy'
"""
from __future__ import annotations

import json
import os
import sys
import uuid
import unittest
from typing import Any, Dict, List, Optional
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Module-level stubs — must happen before any router import ─────────────────
import unittest.mock as _umock
from pydantic import BaseModel as _PydanticBase
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


class _AnyModel(_PydanticBase):
    model_config = {"extra": "allow"}


# backend.app.db — prevents create_engine(postgres_url) at module load
if "backend.app.db" not in sys.modules:
    _stub_db = _umock.MagicMock()
    _stub_db.SessionLocal = _umock.MagicMock()
    sys.modules["backend.app.db"] = _stub_db

# backend.app.schemas — needs real Pydantic models
if "backend.app.schemas" not in sys.modules:
    _stub_schemas = _umock.MagicMock()
    _stub_schemas.CaseDTO = _AnyModel
    _stub_schemas.CaseDraftDTO = _AnyModel
    _stub_schemas.CaseRequirementsDTO = _AnyModel
    sys.modules["backend.app.schemas"] = _stub_schemas

# Remaining modules only used by other route handlers — MagicMock is enough
for _mod in [
    "backend.app.crud",
    "backend.app.auth_deps",
    "backend.app.services.relocation_plan_view_service",
    "backend.app.services.research",
    "backend.app.services.requirements_builder",
    "backend.app.services.roadmap_builder",
    "backend.app.services.trigger_engine",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _umock.MagicMock()

# ── Now safe to import the routers ───────────────────────────────────────────
import backend.app.routers.cases as cases_router               # noqa: E402
from backend.app.routers.cases import (                        # noqa: E402
    bulk_update_form_fields,
    BulkFieldUpdatePayload,
    FieldUpsertInput,
    _assert_case_access,
    _fetch_single_form_summary,
)

import backend.app.routers.admin_form_templates as aft_router  # noqa: E402
from backend.app.routers.admin_form_templates import (         # noqa: E402
    get_accuracy_report,
)

# ── In-memory SQLite schema ───────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE cases (
    id          TEXT PRIMARY KEY,
    company_id  TEXT,
    employee_id TEXT,
    hr_owner_id TEXT
);
CREATE TABLE form_templates (
    id             TEXT PRIMARY KEY,
    code           TEXT NOT NULL DEFAULT 'TEST-001',
    name           TEXT NOT NULL DEFAULT 'Test Form',
    country        TEXT NOT NULL DEFAULT 'NO',
    authority_code TEXT,
    authority_name TEXT,
    version        TEXT NOT NULL DEFAULT '1.0.0',
    fields         TEXT NOT NULL DEFAULT '[]',
    trigger_rules  TEXT NOT NULL DEFAULT '{}',
    category       TEXT,
    original_pdf_url TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    source_language TEXT NOT NULL DEFAULT 'en'
);
CREATE TABLE case_forms (
    id               TEXT PRIMARY KEY,
    case_id          TEXT NOT NULL,
    form_template_id TEXT NOT NULL,
    person_id        TEXT,
    dependent_id     TEXT,
    status           TEXT NOT NULL DEFAULT 'not_started',
    completion_pct   INTEGER NOT NULL DEFAULT 0,
    deadline         TEXT,
    deadline_trigger TEXT,
    deadline_reminded_at TEXT,
    blocker_form_id  TEXT,
    original_file_url TEXT,
    draft_pdf_url    TEXT,
    submitted_at     TEXT,
    receipt_ref      TEXT,
    rejection_reason TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
    id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id  TEXT NOT NULL,
    field_id      TEXT NOT NULL,
    value         TEXT,
    filled_by     TEXT NOT NULL DEFAULT 'ai',
    ai_confidence REAL,
    reviewed      INTEGER NOT NULL DEFAULT 0,
    overridden    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (case_form_id, field_id)
);
CREATE TABLE field_value_overrides (
    id                  TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id        TEXT NOT NULL,
    form_template_id    TEXT NOT NULL,
    field_id            TEXT NOT NULL,
    original_value      TEXT,
    corrected_value     TEXT,
    original_confidence REAL,
    overridden_by       TEXT NOT NULL,
    created_at          TEXT DEFAULT (datetime('now'))
);
"""

_TEMPLATE_FIELDS = json.dumps([
    {"id": "previous_address", "label": "Previous address",
     "type": "text", "required": True, "position": 1,
     "prefill_source": None, "requires_original": False, "options": None},
    {"id": "current_city", "label": "Current city",
     "type": "text", "required": False, "position": 2,
     "prefill_source": None, "requires_original": False, "options": None},
])


def _uuid() -> str:
    return str(uuid.uuid4())


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    return engine


def _seed(engine, *, ai_value: str = "Paris", ai_confidence: float = 0.85,
          code: str = "UTL-2011"):
    """
    Insert one case + form_template + case_form + one AI-prefilled 'previous_address'.
    Returns ids dict.
    """
    case_id = _uuid()
    tmpl_id = _uuid()
    cf_id   = _uuid()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": case_id})
        conn.execute(text(
            "INSERT INTO form_templates (id,code,name,fields) VALUES (:id,:c,:n,:f)"
        ), {"id": tmpl_id, "c": code, "n": "Test Form", "f": _TEMPLATE_FIELDS})
        conn.execute(text(
            "INSERT INTO case_forms (id,case_id,form_template_id,status) "
            "VALUES (:id,:cid,:tid,'in_progress')"
        ), {"id": cf_id, "cid": case_id, "tid": tmpl_id})
        conn.execute(text(
            "INSERT INTO case_form_field_values "
            "(id,case_form_id,field_id,value,filled_by,ai_confidence,reviewed,overridden)"
            " VALUES (:id,:cf,'previous_address',:v,'ai',:conf,0,0)"
        ), {"id": _uuid(), "cf": cf_id, "v": ai_value, "conf": ai_confidence})
    return {"case_id": case_id, "tmpl_id": tmpl_id, "cf_id": cf_id}


# ── Test base ─────────────────────────────────────────────────────────────────

class OverrideTestBase(unittest.TestCase):
    def setUp(self):
        self.engine = _make_engine()
        # Patch the router-level engine references
        self._patcher_cases = mock.patch.object(
            cases_router.main_db, "engine", self.engine
        )
        self._patcher_aft = mock.patch.object(
            aft_router.db, "engine", self.engine
        )
        self._patcher_cases.start()
        self._patcher_aft.start()

    def tearDown(self):
        self._patcher_cases.stop()
        self._patcher_aft.stop()

    def _call_bulk_update(self, case_id: str, form_id: str,
                          fields: Dict[str, Any], role: str = "employee") -> None:
        """Call bulk_update_form_fields directly with a synthetic user."""
        user = {"id": _uuid(), "role": role, "is_admin": False}
        payload = BulkFieldUpdatePayload(
            fields=[FieldUpsertInput(field_id=k, value=v) for k, v in fields.items()]
        )
        with mock.patch.object(cases_router, "_assert_case_access", return_value=None), \
             mock.patch.object(cases_router, "_fetch_single_form_summary",
                               return_value=mock.MagicMock()):
            bulk_update_form_fields(case_id, form_id, payload, user)


# ── Override capture tests ────────────────────────────────────────────────────

class TestOverrideCapture(OverrideTestBase):

    def test_override_captured_when_replacing_ai_value(self):
        ids = _seed(self.engine)
        self._call_bulk_update(ids["case_id"], ids["cf_id"],
                               {"previous_address": "Lyon"}, role="employee")

        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM field_value_overrides WHERE case_form_id=:cf"),
                {"cf": ids["cf_id"]},
            ).mappings().all()

        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["field_id"], "previous_address")
        self.assertEqual(r["original_value"], "Paris")
        self.assertEqual(r["corrected_value"], "Lyon")
        self.assertAlmostEqual(float(r["original_confidence"]), 0.85, places=2)
        self.assertEqual(r["overridden_by"], "employee")
        self.assertEqual(r["form_template_id"], ids["tmpl_id"])

    def test_no_override_for_new_field_with_no_prior_value(self):
        ids = _seed(self.engine)
        self._call_bulk_update(ids["case_id"], ids["cf_id"],
                               {"current_city": "Oslo"}, role="employee")

        with self.engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM field_value_overrides WHERE case_form_id=:cf"),
                {"cf": ids["cf_id"]},
            ).scalar()
        self.assertEqual(count, 0)

    def test_hr_role_attributed_as_specialist(self):
        ids = _seed(self.engine)
        self._call_bulk_update(ids["case_id"], ids["cf_id"],
                               {"previous_address": "Nice"}, role="hr")

        with self.engine.connect() as conn:
            r = conn.execute(
                text("SELECT overridden_by FROM field_value_overrides WHERE case_form_id=:cf"),
                {"cf": ids["cf_id"]},
            ).mappings().first()
        self.assertEqual(r["overridden_by"], "specialist")

    def test_admin_role_attributed_as_specialist(self):
        ids = _seed(self.engine)
        self._call_bulk_update(ids["case_id"], ids["cf_id"],
                               {"previous_address": "Bordeaux"}, role="admin")

        with self.engine.connect() as conn:
            r = conn.execute(
                text("SELECT overridden_by FROM field_value_overrides WHERE case_form_id=:cf"),
                {"cf": ids["cf_id"]},
            ).mappings().first()
        self.assertEqual(r["overridden_by"], "specialist")

    def test_only_first_correction_generates_override_record(self):
        """
        Once filled_by = 'employee', subsequent saves don't create new override rows
        (because was_ai=False after the first write).
        """
        ids = _seed(self.engine)
        for city in ["Lyon", "Marseille", "Toulouse"]:
            self._call_bulk_update(ids["case_id"], ids["cf_id"],
                                   {"previous_address": city}, role="employee")

        with self.engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM field_value_overrides WHERE case_form_id=:cf"),
                {"cf": ids["cf_id"]},
            ).scalar()
        # Only the first replacement (AI → employee) creates an override record
        self.assertEqual(count, 1)

    def test_field_value_is_updated_after_override(self):
        ids = _seed(self.engine)
        self._call_bulk_update(ids["case_id"], ids["cf_id"],
                               {"previous_address": "Lyon"}, role="employee")

        with self.engine.connect() as conn:
            r = conn.execute(
                text("SELECT value, filled_by, overridden FROM case_form_field_values "
                     "WHERE case_form_id=:cf AND field_id='previous_address'"),
                {"cf": ids["cf_id"]},
            ).mappings().first()
        self.assertEqual(r["value"], "Lyon")
        self.assertEqual(r["filled_by"], "employee")
        self.assertEqual(int(r["overridden"]), 1)


# ── Accuracy report tests ─────────────────────────────────────────────────────

class TestAccuracyReport(OverrideTestBase):

    def _add_override_row(self, cf_id: str, tmpl_id: str, field_id: str,
                          orig_conf: float = 0.85) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO field_value_overrides "
                "(id,case_form_id,form_template_id,field_id,"
                " original_value,corrected_value,original_confidence,overridden_by)"
                " VALUES (:id,:cf,:ti,:fi,'old','new',:conf,'employee')"
            ), {"id": _uuid(), "cf": cf_id, "ti": tmpl_id,
                "fi": field_id, "conf": orig_conf})

    def _get_report(self) -> List[Any]:
        admin_user = {"id": _uuid(), "role": "admin", "is_admin": True}
        with mock.patch.object(aft_router, "require_admin",
                               return_value=lambda: admin_user):
            return get_accuracy_report(admin_user)

    def test_report_shows_correct_override_rate(self):
        ids = _seed(self.engine)
        self._add_override_row(ids["cf_id"], ids["tmpl_id"], "previous_address")

        results = self._get_report()
        row = next((r for r in results if r.field_id == "previous_address"), None)
        self.assertIsNotNone(row)
        self.assertEqual(row.total_ai_fills, 1)
        self.assertEqual(row.overrides, 1)
        self.assertEqual(row.override_rate_pct, 100)

    def test_report_flags_low_accuracy(self):
        ids = _seed(self.engine)
        self._add_override_row(ids["cf_id"], ids["tmpl_id"], "previous_address")

        results = self._get_report()
        row = next((r for r in results if r.field_id == "previous_address"), None)
        self.assertEqual(row.accuracy_flag, "low_accuracy")

    def test_report_no_flag_when_zero_overrides(self):
        ids = _seed(self.engine)  # AI fill exists, no overrides

        results = self._get_report()
        row = next((r for r in results if r.field_id == "previous_address"), None)
        self.assertIsNotNone(row)
        self.assertIsNone(row.accuracy_flag)
        self.assertEqual(row.override_rate_pct, 0)

    def test_report_field_edit_url_contains_template_and_field(self):
        ids = _seed(self.engine)
        self._add_override_row(ids["cf_id"], ids["tmpl_id"], "previous_address")

        results = self._get_report()
        row = next((r for r in results if r.field_id == "previous_address"), None)
        self.assertIn(ids["tmpl_id"], row.field_edit_url)
        self.assertIn("previous_address", row.field_edit_url)

    def test_validation_criterion_five_overrides_utl2011(self):
        """
        [P4-6 validation] After 5 overrides of 'previous_address' in UTL-2011,
        admin report shows override_rate=100% with 'low_accuracy' flag.
        """
        ids = _seed(self.engine, ai_value="Paris", ai_confidence=0.85, code="UTL-2011")
        for _ in range(5):
            self._add_override_row(ids["cf_id"], ids["tmpl_id"],
                                   "previous_address", orig_conf=0.85)

        results = self._get_report()
        row = next((r for r in results if r.field_id == "previous_address"), None)
        self.assertIsNotNone(row, "previous_address must appear in accuracy report")
        self.assertEqual(row.form_code, "UTL-2011")
        self.assertEqual(row.override_rate_pct, 100)
        self.assertEqual(row.accuracy_flag, "low_accuracy")
        self.assertIn(ids["tmpl_id"], row.field_edit_url)
        self.assertIn("previous_address", row.field_edit_url)

    def test_report_two_fields_independent_rates(self):
        """
        Two fields in the same form can have different override rates.
        """
        ids = _seed(self.engine)
        # Also insert an AI fill for 'current_city'
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO case_form_field_values "
                "(id,case_form_id,field_id,value,filled_by,ai_confidence,reviewed,overridden)"
                " VALUES (:id,:cf,'current_city','Oslo','ai',0.7,0,0)"
            ), {"id": _uuid(), "cf": ids["cf_id"]})
        # Override only 'previous_address'
        self._add_override_row(ids["cf_id"], ids["tmpl_id"], "previous_address")

        results = self._get_report()
        addr_row = next((r for r in results if r.field_id == "previous_address"), None)
        city_row = next((r for r in results if r.field_id == "current_city"), None)

        self.assertEqual(addr_row.override_rate_pct, 100)
        self.assertEqual(addr_row.accuracy_flag, "low_accuracy")
        self.assertEqual(city_row.override_rate_pct, 0)
        self.assertIsNone(city_row.accuracy_flag)


if __name__ == "__main__":
    unittest.main()
