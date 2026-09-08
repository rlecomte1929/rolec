"""
Tests for [P2-2] Field value storage and bulk update API.

Covers:
  GET  /{case_id}/forms/{form_id}/fields   → list fields merged with stored values
  PUT  /{case_id}/forms/{form_id}/fields   → bulk upsert (employee save)
  PATCH /{case_id}/forms/{form_id}         → status transitions (ready / submitted)

Pattern:
  - SQLite in-memory DB
  - mock.patch.object on cases_router.main_db to swap the engine
  - mock.patch.object on the _assert_case_access helper to bypass auth
  - Handler functions called directly (no HTTP layer)
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional
from unittest import mock

from sqlalchemy import create_engine, text
from fastapi import HTTPException

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Pre-import stubs ─────────────────────────────────────────────────────────
# cases.py imports `from ..db import SessionLocal` at module level, which calls
# create_engine(postgres_url) and requires psycopg2.  We stub that module in
# sys.modules before the router is imported so the sandbox (no psycopg2) can
# still load the module and we can exercise only the P2-2 handlers.
import unittest.mock as _umock  # noqa: E402
from pydantic import BaseModel as _PydanticBase  # noqa: E402


class _AnyModel(_PydanticBase):
    """Permissive stand-in for FastAPI response models (Pydantic v2)."""
    model_config = {"extra": "allow"}


if "backend.app.db" not in sys.modules:
    _stub_db = _umock.MagicMock()
    _stub_db.SessionLocal = _umock.MagicMock()
    sys.modules["backend.app.db"] = _stub_db

# schemas needs real Pydantic models so FastAPI's route registration succeeds.
if "backend.app.schemas" not in sys.modules:
    _stub_schemas = _umock.MagicMock()
    _stub_schemas.CaseDTO = _AnyModel
    _stub_schemas.CaseDraftDTO = _AnyModel
    _stub_schemas.CaseRequirementsDTO = _AnyModel
    sys.modules["backend.app.schemas"] = _stub_schemas

# crud / auth_deps / services are only used by non-P2-2 route handlers;
# MagicMock stubs are enough for module import.
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

# ── Now we can safely import the router ──────────────────────────────────────
import backend.app.routers.cases as cases_router  # noqa: E402
from backend.app.routers.cases import (  # noqa: E402
    get_form_fields,
    bulk_update_form_fields,
    patch_form_status,
    BulkFieldUpdatePayload,
    FieldUpsertInput,
    FormStatusPatchPayload,
    _compute_completion,
)


# ─────────────────────────────────────────────────────────────────────────────
# SQLite schema — mirrors only what the three endpoints read / write
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE cases (
    id          TEXT PRIMARY KEY,
    company_id  TEXT,
    employee_id TEXT,
    hr_owner_id TEXT
);
CREATE TABLE profiles (
    id        TEXT PRIMARY KEY,
    full_name TEXT,
    email     TEXT,
    company_id TEXT
);
CREATE TABLE form_templates (
    id             TEXT PRIMARY KEY,
    code           TEXT NOT NULL,
    name           TEXT NOT NULL DEFAULT 'Test Form',
    authority_code TEXT,
    authority_name TEXT,
    country        TEXT NOT NULL DEFAULT 'NO',
    category       TEXT,
    version        TEXT NOT NULL DEFAULT '1.0.0',
    fields         TEXT NOT NULL DEFAULT '[]',
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
    blocker_form_id  TEXT,
    original_file_url TEXT,
    draft_pdf_url    TEXT,
    submitted_at      TEXT,
    receipt_ref       TEXT,
    rejection_reason  TEXT,
    deadline_reminded_at TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
    id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id  TEXT NOT NULL,
    field_id      TEXT NOT NULL,
    value         TEXT,
    filled_by     TEXT NOT NULL DEFAULT 'ai',
    ai_confidence REAL,
    source        TEXT,
    reviewed      INTEGER NOT NULL DEFAULT 0,
    overridden    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (case_form_id, field_id)
);
CREATE TABLE case_dependents (
    id           TEXT PRIMARY KEY,
    case_id      TEXT NOT NULL,
    relationship TEXT NOT NULL,
    full_name    TEXT
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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())


DUMMY_USER: Dict[str, Any] = {"id": _uuid(), "role": "employee", "is_admin": False}


def _make_fields(count: int = 3, required_all: bool = True) -> List[Dict]:
    return [
        {
            "id": f"field_{i}",
            "label": f"Field {i}",
            "type": "text",
            "required": required_all,
            "position": i,
            "prefill_source": f"profile.field_{i}",
            "requires_original": False,
        }
        for i in range(1, count + 1)
    ]


def _insert_case(conn, case_id: str) -> None:
    conn.execute(text(
        "INSERT INTO cases (id) VALUES (:id)"
    ), {"id": case_id})


def _insert_template(conn, template_id: str, fields: List[Dict]) -> str:
    conn.execute(text(
        "INSERT INTO form_templates (id, code, name, country, version, fields) "
        "VALUES (:id, :code, :name, :country, :ver, :fields)"
    ), {"id": template_id, "code": "TEST-001", "name": "Test Form",
        "country": "NO", "ver": "1.0.0", "fields": json.dumps(fields)})
    return template_id


def _insert_case_form(
    conn,
    cf_id: str,
    case_id: str,
    template_id: str,
    status: str = "not_started",
    person_id: Optional[str] = None,
) -> None:
    conn.execute(text(
        "INSERT INTO case_forms "
        "(id, case_id, form_template_id, person_id, status, completion_pct) "
        "VALUES (:id, :cid, :tid, :pid, :status, 0)"
    ), {"id": cf_id, "cid": case_id, "tid": template_id,
        "pid": person_id, "status": status})


def _insert_field_value(
    conn,
    cf_id: str,
    field_id: str,
    value: str,
    filled_by: str = "ai",
    reviewed: bool = False,
    overridden: bool = False,
) -> None:
    conn.execute(text(
        "INSERT INTO case_form_field_values "
        "(id, case_form_id, field_id, value, filled_by, reviewed, overridden) "
        "VALUES (lower(hex(randomblob(16))), :cid, :fid, :val, :fb, :rev, :ov)"
    ), {"cid": cf_id, "fid": field_id, "val": value,
        "fb": filled_by, "rev": int(reviewed), "ov": int(overridden)})


def _get_form_row(conn, cf_id: str) -> Dict[str, Any]:
    row = conn.execute(
        text("SELECT * FROM case_forms WHERE id = :id"), {"id": cf_id}
    ).mappings().first()
    return dict(row) if row else {}


def _get_field_value(conn, cf_id: str, field_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text("SELECT * FROM case_form_field_values "
             "WHERE case_form_id = :cid AND field_id = :fid"),
        {"cid": cf_id, "fid": field_id},
    ).mappings().first()
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Test suite
# ─────────────────────────────────────────────────────────────────────────────

class FieldValueApiTests(unittest.TestCase):

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

        # Patch main_db.engine to point at our SQLite instance
        self.engine_patcher = mock.patch.object(
            cases_router.main_db, "engine", self.engine
        )
        self.engine_patcher.start()

        # Patch _assert_case_access to be a no-op (tested separately)
        self.auth_patcher = mock.patch.object(
            cases_router, "_assert_case_access", return_value=None
        )
        self.auth_patcher.start()

    def tearDown(self):
        self.engine_patcher.stop()
        self.auth_patcher.stop()
        self.engine.dispose()

    # ── _compute_completion helper ────────────────────────────────────────────

    def test_compute_completion_all_required_filled(self):
        fields = _make_fields(3, required_all=True)
        stored = {"field_1": "A", "field_2": "B", "field_3": "C"}
        self.assertEqual(_compute_completion(fields, stored), 100)

    def test_compute_completion_partially_filled(self):
        fields = _make_fields(4, required_all=True)
        stored = {"field_1": "A", "field_2": "B"}
        self.assertEqual(_compute_completion(fields, stored), 50)

    def test_compute_completion_none_filled(self):
        fields = _make_fields(2, required_all=True)
        self.assertEqual(_compute_completion(fields, {}), 0)

    def test_compute_completion_no_required_uses_all_fields(self):
        fields = _make_fields(4, required_all=False)
        stored = {"field_1": "A", "field_2": "B"}
        # 2 of 4 filled
        self.assertEqual(_compute_completion(fields, stored), 50)

    def test_compute_completion_empty_string_not_counted(self):
        fields = _make_fields(2, required_all=True)
        stored = {"field_1": "", "field_2": "  "}
        # Both non-empty checks: "" and "  " are truthy strings but stored as-is.
        # Our helper uses `not in (None, "")` — so "" is not counted, "  " IS counted.
        # field_2 has value "  " (non-empty string) so it IS counted.
        self.assertEqual(_compute_completion(fields, stored), 50)

    # ── GET /fields — list fields merged with stored values ───────────────────

    def test_get_fields_returns_all_template_fields(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        fields = _make_fields(3)
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, fields)
            _insert_case_form(conn, cf_id, case_id, tmpl_id)

        result = get_form_fields(case_id, cf_id, DUMMY_USER)
        self.assertEqual(len(result), 3)
        self.assertIsNone(result[0].value)
        self.assertIsNone(result[0].filled_by)

    def test_get_fields_merges_stored_values(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        fields = _make_fields(2)
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, fields)
            _insert_case_form(conn, cf_id, case_id, tmpl_id)
            _insert_field_value(conn, cf_id, "field_1", "Paris", filled_by="ai",
                                reviewed=False)

        result = get_form_fields(case_id, cf_id, DUMMY_USER)
        by_id = {item.field_id: item for item in result}
        self.assertEqual(by_id["field_1"].value, "Paris")
        self.assertEqual(by_id["field_1"].filled_by, "ai")
        self.assertFalse(by_id["field_1"].reviewed)
        self.assertIsNone(by_id["field_2"].value)

    def test_get_fields_404_for_wrong_case(self):
        case_id, other_case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_case(conn, other_case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, other_case_id, tmpl_id)

        with self.assertRaises(HTTPException) as ctx:
            get_form_fields(case_id, cf_id, DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_fields_sorted_by_position(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        fields = [
            {"id": "z_field", "label": "Z", "type": "text", "required": True,
             "position": 3, "prefill_source": None, "requires_original": False},
            {"id": "a_field", "label": "A", "type": "text", "required": True,
             "position": 1, "prefill_source": None, "requires_original": False},
        ]
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, fields)
            _insert_case_form(conn, cf_id, case_id, tmpl_id)

        result = get_form_fields(case_id, cf_id, DUMMY_USER)
        self.assertEqual(result[0].field_id, "a_field")
        self.assertEqual(result[1].field_id, "z_field")

    # ── PUT /fields — bulk upsert ────────────────────────────────────────────

    def test_put_fields_inserts_new_values(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(2))
            _insert_case_form(conn, cf_id, case_id, tmpl_id)

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="Alice"),
            FieldUpsertInput(field_id="field_2", value="Smith"),
        ])
        bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        with self.engine.connect() as conn:
            fv1 = _get_field_value(conn, cf_id, "field_1")
            fv2 = _get_field_value(conn, cf_id, "field_2")
        self.assertEqual(fv1["value"], "Alice")
        self.assertEqual(fv1["filled_by"], "employee")
        self.assertTrue(fv1["reviewed"])
        self.assertFalse(bool(fv1["overridden"]))
        self.assertEqual(fv2["value"], "Smith")

    def test_put_fields_sets_overridden_when_replacing_ai_value(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id)
            _insert_field_value(conn, cf_id, "field_1", "AI-value", filled_by="ai")

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="Human-value"),
        ])
        bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        with self.engine.connect() as conn:
            fv = _get_field_value(conn, cf_id, "field_1")
        self.assertEqual(fv["value"], "Human-value")
        self.assertEqual(fv["filled_by"], "employee")
        self.assertTrue(bool(fv["overridden"]))

    def test_put_fields_does_not_set_overridden_for_new_field(self):
        """Fields with no prior value should have overridden=False."""
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id)

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="Brand new"),
        ])
        bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        with self.engine.connect() as conn:
            fv = _get_field_value(conn, cf_id, "field_1")
        self.assertFalse(bool(fv["overridden"]))

    def test_put_fields_does_not_set_overridden_when_replacing_employee_value(self):
        """overridden should only flip to True when an AI value is replaced."""
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id)
            _insert_field_value(conn, cf_id, "field_1", "first-human", filled_by="employee")

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="second-human"),
        ])
        bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        with self.engine.connect() as conn:
            fv = _get_field_value(conn, cf_id, "field_1")
        self.assertFalse(bool(fv["overridden"]))

    def test_put_fields_recomputes_completion_pct(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(4, required_all=True))
            _insert_case_form(conn, cf_id, case_id, tmpl_id)

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="A"),
            FieldUpsertInput(field_id="field_2", value="B"),
        ])
        bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        with self.engine.connect() as conn:
            row = _get_form_row(conn, cf_id)
        self.assertEqual(row["completion_pct"], 50)

    def test_put_fields_advances_status_from_not_started(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id, status="not_started")

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="X"),
        ])
        bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        with self.engine.connect() as conn:
            row = _get_form_row(conn, cf_id)
        self.assertEqual(row["status"], "in_progress")

    def test_put_fields_does_not_regress_status_from_auto_filled(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id, status="auto_filled")

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="X"),
        ])
        bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        with self.engine.connect() as conn:
            row = _get_form_row(conn, cf_id)
        # Status must NOT regress back to not_started or in_progress
        self.assertEqual(row["status"], "auto_filled")

    def test_put_fields_404_for_missing_form(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="X"),
        ])
        with self.assertRaises(HTTPException) as ctx:
            bulk_update_form_fields(case_id, _uuid(), payload, DUMMY_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_put_fields_returns_case_form_summary(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id)

        payload = BulkFieldUpdatePayload(fields=[
            FieldUpsertInput(field_id="field_1", value="Hello"),
        ])
        result = bulk_update_form_fields(case_id, cf_id, payload, DUMMY_USER)

        from backend.app.routers.cases import CaseFormSummary
        self.assertIsInstance(result, CaseFormSummary)
        self.assertEqual(result.id, cf_id)

    # ── PATCH /forms/{form_id} — status transitions ───────────────────────────

    def test_patch_status_ready_succeeds_when_all_required_filled(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(2, required_all=True))
            _insert_case_form(conn, cf_id, case_id, tmpl_id, status="in_progress")
            _insert_field_value(conn, cf_id, "field_1", "Val1", filled_by="employee")
            _insert_field_value(conn, cf_id, "field_2", "Val2", filled_by="employee")

        result = patch_form_status(
            case_id, cf_id,
            FormStatusPatchPayload(status="ready"),
            DUMMY_USER,
        )
        self.assertEqual(result.status, "ready")

    def test_patch_status_ready_422_when_required_field_missing(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(3, required_all=True))
            _insert_case_form(conn, cf_id, case_id, tmpl_id, status="in_progress")
            # Only fill 2 of 3 required fields
            _insert_field_value(conn, cf_id, "field_1", "A", filled_by="employee")
            _insert_field_value(conn, cf_id, "field_2", "B", filled_by="employee")

        with self.assertRaises(HTTPException) as ctx:
            patch_form_status(
                case_id, cf_id,
                FormStatusPatchPayload(status="ready"),
                DUMMY_USER,
            )
        self.assertEqual(ctx.exception.status_code, 422)
        # detail should include the missing field id
        detail = ctx.exception.detail
        self.assertIn("missing_fields", detail)
        self.assertIn("field_3", detail["missing_fields"])

    def test_patch_status_ready_422_on_empty_value(self):
        """A field with value='' is not counted as filled."""
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1, required_all=True))
            _insert_case_form(conn, cf_id, case_id, tmpl_id, status="in_progress")
            _insert_field_value(conn, cf_id, "field_1", "", filled_by="employee")

        with self.assertRaises(HTTPException) as ctx:
            patch_form_status(
                case_id, cf_id,
                FormStatusPatchPayload(status="ready"),
                DUMMY_USER,
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_patch_status_submitted_stores_receipt_ref(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id, status="ready")

        result = patch_form_status(
            case_id, cf_id,
            FormStatusPatchPayload(status="submitted", receipt_ref="REC-2026-001"),
            DUMMY_USER,
        )
        self.assertEqual(result.status, "submitted")
        self.assertEqual(result.receipt_ref, "REC-2026-001")

        with self.engine.connect() as conn:
            row = _get_form_row(conn, cf_id)
        self.assertEqual(row["receipt_ref"], "REC-2026-001")
        self.assertIsNotNone(row["submitted_at"])

    def test_patch_status_submitted_422_without_receipt_ref(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id, status="ready")

        with self.assertRaises(HTTPException) as ctx:
            patch_form_status(
                case_id, cf_id,
                FormStatusPatchPayload(status="submitted"),
                DUMMY_USER,
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_patch_status_invalid_transition_422(self):
        case_id, cf_id, tmpl_id = _uuid(), _uuid(), _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)
            _insert_template(conn, tmpl_id, _make_fields(1))
            _insert_case_form(conn, cf_id, case_id, tmpl_id)

        with self.assertRaises(HTTPException) as ctx:
            patch_form_status(
                case_id, cf_id,
                FormStatusPatchPayload(status="approved"),
                DUMMY_USER,
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_patch_status_404_for_missing_form(self):
        case_id = _uuid()
        with self.engine.begin() as conn:
            _insert_case(conn, case_id)

        with self.assertRaises(HTTPException) as ctx:
            patch_form_status(
                case_id, _uuid(),
                FormStatusPatchPayload(status="ready"),
                DUMMY_USER,
            )
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
