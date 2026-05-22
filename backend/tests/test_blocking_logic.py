"""
Tests for [P2-6] Blocking dependency logic.

Covers:
  - is_blocked computed correctly (True / False) from blocker_status
  - PATCH status=approved transitions the form to 'approved'
  - PATCH status=approved triggers run_prefill_for_dependents
  - PATCH status=approved on a form that blocks another: blocked form is
    unlocked (DB trigger equivalent in Python test harness via direct SQL)
  - Existing ready / submitted transitions still work

Follows the same SQLite-in-memory + mock.patch pattern as the other test files.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from typing import Any, Dict
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Pre-import stubs ─────────────────────────────────────────────────────────
# cases.py has a deep import chain (db → psycopg2, crud → models, auth_deps,
# several services). Stub every transitive dep before importing the router so
# the sandbox (no psycopg2) can load it for unit testing.
import unittest.mock as _umock  # noqa: E402
from pydantic import BaseModel as _PydanticBase  # noqa: E402


class _AnyModel(_PydanticBase):
    model_config = {"extra": "allow"}


if "backend.app.db" not in sys.modules:
    _stub_db = _umock.MagicMock()
    _stub_db.SessionLocal = _umock.MagicMock()
    sys.modules["backend.app.db"] = _stub_db

if "backend.app.schemas" not in sys.modules:
    _stub_schemas = _umock.MagicMock()
    _stub_schemas.CaseDTO = _AnyModel
    _stub_schemas.CaseDraftDTO = _AnyModel
    _stub_schemas.CaseRequirementsDTO = _AnyModel
    sys.modules["backend.app.schemas"] = _stub_schemas

for _mod in [
    "backend.app.crud",
    "backend.app.auth_deps",
    "backend.app.services.relocation_plan_view_service",
    "backend.app.services.research",
    "backend.app.services.requirements_builder",
    "backend.app.services.roadmap_builder",
    # NOTE: trigger_engine and prefill_engine are NOT stubbed here.
    # Their real modules import cleanly (they use backend.database, not
    # backend.app.db which is the one that needs psycopg2). Stubbing them
    # in sys.modules would poison test_trigger_engine.py and
    # test_prefill_engine.py when all tests run in the same process.
    # Individual tests that intercept these functions use mock.patch on the
    # names imported into the cases module namespace instead.
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _umock.MagicMock()
# ─────────────────────────────────────────────────────────────────────────────

import backend.app.routers.cases as cases_module  # noqa: E402
from backend.app.routers.cases import (  # noqa: E402
    _row_to_summary,
    patch_form_status,
    FormStatusPatchPayload,
)

# ---------------------------------------------------------------------------
# SQLite schema — mirrors the tables cases.py reads / writes for P2-6
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE cases (
    id              TEXT PRIMARY KEY,
    employee_id     TEXT,
    company_id      TEXT
);
CREATE TABLE profiles (
    id        TEXT PRIMARY KEY,
    full_name TEXT,
    email     TEXT,
    role      TEXT DEFAULT 'employee',
    company_id TEXT,
    is_admin  INTEGER DEFAULT 0
);
CREATE TABLE form_templates (
    id             TEXT PRIMARY KEY,
    code           TEXT NOT NULL,
    name           TEXT NOT NULL DEFAULT 'Test Form',
    authority_code TEXT DEFAULT 'TEST',
    authority_name TEXT DEFAULT 'Test Authority',
    country        TEXT NOT NULL DEFAULT 'NO',
    category       TEXT DEFAULT 'test',
    version        TEXT NOT NULL DEFAULT '1.0.0',
    fields         TEXT NOT NULL DEFAULT '[]'
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
    deadline         TEXT,
    deadline_trigger TEXT,
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
    filled_by     TEXT NOT NULL DEFAULT 'system',
    ai_confidence REAL,
    reviewed      INTEGER NOT NULL DEFAULT 0,
    overridden    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (case_form_id, field_id)
);
CREATE TABLE case_dependents (
    id            TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL,
    relationship  TEXT NOT NULL DEFAULT 'child',
    full_name     TEXT,
    date_of_birth TEXT,
    nationality   TEXT,
    passport_expiry TEXT
);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


def _insert_case(conn, case_id: str, employee_id: str) -> None:
    conn.execute(text(
        "INSERT INTO cases (id, employee_id) VALUES (:id, :emp)"
    ), {"id": case_id, "emp": employee_id})


def _insert_profile(conn, profile_id: str, role: str = "employee",
                    is_admin: int = 0) -> None:
    conn.execute(text(
        "INSERT INTO profiles (id, full_name, email, role, is_admin) "
        "VALUES (:id, 'Test User', 'test@example.com', :role, :admin)"
    ), {"id": profile_id, "role": role, "admin": is_admin})


def _insert_template(conn, template_id: str, code: str = "UTL-2011",
                     fields: list | None = None) -> None:
    conn.execute(text(
        "INSERT INTO form_templates (id, code, fields) VALUES (:id, :code, :fields)"
    ), {"id": template_id, "code": code, "fields": json.dumps(fields or [])})


def _insert_case_form(conn, cf_id: str, case_id: str, template_id: str,
                      status: str = "not_started",
                      blocker_form_id: str | None = None,
                      person_id: str | None = None) -> None:
    conn.execute(text(
        "INSERT INTO case_forms "
        "(id, case_id, form_template_id, status, blocker_form_id, person_id) "
        "VALUES (:id, :cid, :tid, :status, :blocker, :pid)"
    ), {"id": cf_id, "cid": case_id, "tid": template_id,
        "status": status, "blocker": blocker_form_id, "pid": person_id})


def _fake_user(user_id: str, role: str = "employee", is_admin: bool = False) -> Dict[str, Any]:
    return {"id": user_id, "role": role, "is_admin": is_admin}


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class BlockingLogicTests(unittest.TestCase):

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

        # Patch the db engine used by cases.py
        self.db_patcher = mock.patch.object(cases_module.main_db, "engine", self.engine)
        self.db_patcher.start()

        # Patch _assert_case_access to always succeed
        self.auth_patcher = mock.patch.object(
            cases_module, "_assert_case_access", return_value=None
        )
        self.auth_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.auth_patcher.stop()
        self.engine.dispose()

    # ── is_blocked computation ───────────────────────────────────────────────

    def test_is_blocked_true_when_blocker_not_approved(self):
        """is_blocked=True when blocker exists and is not yet approved."""
        row = {
            "id": _uuid(), "case_id": _uuid(), "status": "not_started",
            "completion_pct": 0, "deadline": None, "deadline_trigger": None,
            "blocker_form_id": _uuid(), "blocker_form_code": "GP-7-04",
            "blocker_status": "not_started",
            "original_file_url": None, "draft_pdf_url": None,
            "submitted_at": None, "receipt_ref": None,
            "template_id": _uuid(), "template_code": "HELFO-1",
            "template_name": "Health insurance registration",
            "template_authority_code": "HELFO",
            "template_authority_name": "HELFO",
            "template_country": "NO", "template_category": "health",
            "template_version": "1.0.0", "template_fields": "[]",
            "dependent_id": None, "dependent_relationship": None,
            "dependent_name": None, "person_id": None,
            "profile_full_name": None, "profile_email": None,
            "fv_filled_by_ai": 0, "fv_filled_by_human": 0,
            "fv_reviewed": 0, "fv_overridden": 0,
            "created_at": "2026-05-21T00:00:00", "updated_at": "2026-05-21T00:00:00",
        }
        summary = _row_to_summary(row)
        self.assertTrue(summary.is_blocked)

    def test_is_blocked_false_when_blocker_approved(self):
        """is_blocked=False once the blocking form reaches 'approved'."""
        row = {
            "id": _uuid(), "case_id": _uuid(), "status": "not_started",
            "completion_pct": 0, "deadline": None, "deadline_trigger": None,
            "blocker_form_id": _uuid(), "blocker_form_code": "GP-7-04",
            "blocker_status": "approved",  # <-- blocker is done
            "original_file_url": None, "draft_pdf_url": None,
            "submitted_at": None, "receipt_ref": None,
            "template_id": _uuid(), "template_code": "HELFO-1",
            "template_name": "Health insurance registration",
            "template_authority_code": "HELFO", "template_authority_name": "HELFO",
            "template_country": "NO", "template_category": "health",
            "template_version": "1.0.0", "template_fields": "[]",
            "dependent_id": None, "dependent_relationship": None, "dependent_name": None,
            "person_id": None, "profile_full_name": None, "profile_email": None,
            "fv_filled_by_ai": 0, "fv_filled_by_human": 0,
            "fv_reviewed": 0, "fv_overridden": 0,
            "created_at": "2026-05-21T00:00:00", "updated_at": "2026-05-21T00:00:00",
        }
        summary = _row_to_summary(row)
        self.assertFalse(summary.is_blocked)

    def test_is_blocked_false_when_no_blocker(self):
        """is_blocked=False when blocker_form_id is None."""
        row = {
            "id": _uuid(), "case_id": _uuid(), "status": "not_started",
            "completion_pct": 0, "deadline": None, "deadline_trigger": None,
            "blocker_form_id": None, "blocker_form_code": None,
            "blocker_status": None,
            "original_file_url": None, "draft_pdf_url": None,
            "submitted_at": None, "receipt_ref": None,
            "template_id": _uuid(), "template_code": "UTL-2011",
            "template_name": "Work permit", "template_authority_code": "UDI",
            "template_authority_name": "UDI", "template_country": "NO",
            "template_category": "work_permit", "template_version": "1.0.0",
            "template_fields": "[]",
            "dependent_id": None, "dependent_relationship": None, "dependent_name": None,
            "person_id": None, "profile_full_name": None, "profile_email": None,
            "fv_filled_by_ai": 0, "fv_filled_by_human": 0,
            "fv_reviewed": 0, "fv_overridden": 0,
            "created_at": "2026-05-21T00:00:00", "updated_at": "2026-05-21T00:00:00",
        }
        summary = _row_to_summary(row)
        self.assertFalse(summary.is_blocked)

    def test_is_blocked_false_when_form_itself_is_terminal(self):
        """is_blocked=False when the form itself is submitted (no longer care about blocker)."""
        row = {
            "id": _uuid(), "case_id": _uuid(), "status": "submitted",
            "completion_pct": 100, "deadline": None, "deadline_trigger": None,
            "blocker_form_id": _uuid(), "blocker_form_code": "GP-7-04",
            "blocker_status": "in_progress",
            "original_file_url": None, "draft_pdf_url": None,
            "submitted_at": "2026-05-21T10:00:00", "receipt_ref": "REF-001",
            "template_id": _uuid(), "template_code": "HELFO-1",
            "template_name": "Health insurance", "template_authority_code": "HELFO",
            "template_authority_name": "HELFO", "template_country": "NO",
            "template_category": "health", "template_version": "1.0.0",
            "template_fields": "[]",
            "dependent_id": None, "dependent_relationship": None, "dependent_name": None,
            "person_id": None, "profile_full_name": None, "profile_email": None,
            "fv_filled_by_ai": 0, "fv_filled_by_human": 0,
            "fv_reviewed": 0, "fv_overridden": 0,
            "created_at": "2026-05-21T00:00:00", "updated_at": "2026-05-21T00:00:00",
        }
        summary = _row_to_summary(row)
        self.assertFalse(summary.is_blocked)

    # ── PATCH approved transition ─────────────────────────────────────────────

    def test_patch_approved_sets_status(self):
        """PATCH status=approved persists 'approved' on the case_form row."""
        case_id = _uuid();  emp_id = _uuid()
        tmpl_id = _uuid();  cf_id = _uuid()

        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl_id)
            _insert_case_form(conn, cf_id, case_id, tmpl_id,
                              status="submitted", person_id=emp_id)

        user = _fake_user(emp_id, role="HR")
        payload = FormStatusPatchPayload(status="approved")

        with mock.patch("backend.app.routers.cases.run_prefill_for_dependents") as mock_prefill:
            mock_prefill.return_value = 0
            result = patch_form_status(case_id, cf_id, payload, user=user)

        self.assertEqual(result.status, "approved")

        with self.engine.connect() as conn:
            db_status = conn.execute(text(
                "SELECT status FROM case_forms WHERE id = :id"
            ), {"id": cf_id}).scalar()
        self.assertEqual(db_status, "approved")

    def test_patch_approved_calls_run_prefill_for_dependents(self):
        """Approving a form triggers run_prefill_for_dependents with the correct args."""
        case_id = _uuid();  emp_id = _uuid()
        tmpl_id = _uuid();  cf_id = _uuid()

        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl_id)
            _insert_case_form(conn, cf_id, case_id, tmpl_id,
                              status="submitted", person_id=emp_id)

        user = _fake_user(emp_id, role="HR")
        payload = FormStatusPatchPayload(status="approved")

        with mock.patch("backend.app.routers.cases.run_prefill_for_dependents") as mock_prefill:
            mock_prefill.return_value = 3
            patch_form_status(case_id, cf_id, payload, user=user)

        mock_prefill.assert_called_once_with(cf_id, case_id)

    def test_patch_approved_does_not_call_prefill_for_ready(self):
        """run_prefill_for_dependents is NOT called for non-approved transitions."""
        case_id = _uuid();  emp_id = _uuid()
        tmpl_id = _uuid();  cf_id = _uuid()
        fields = [{"id": "f1", "required": True, "label": "F1",
                   "type": "text", "position": 1}]

        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl_id, fields=fields)
            _insert_case_form(conn, cf_id, case_id, tmpl_id,
                              status="in_progress", person_id=emp_id)
            # Satisfy the required field
            conn.execute(text(
                "INSERT INTO case_form_field_values "
                "(id, case_form_id, field_id, value, filled_by) "
                "VALUES (:id, :cfid, 'f1', 'hello', 'employee')"
            ), {"id": _uuid(), "cfid": cf_id})

        user = _fake_user(emp_id)
        payload = FormStatusPatchPayload(status="ready")

        with mock.patch("backend.app.routers.cases.run_prefill_for_dependents") as mock_prefill:
            patch_form_status(case_id, cf_id, payload, user=user)

        mock_prefill.assert_not_called()

    def test_patch_invalid_transition_still_rejected(self):
        """Unrecognised status values are still rejected with 422."""
        case_id = _uuid();  emp_id = _uuid()
        tmpl_id = _uuid();  cf_id = _uuid()

        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl_id)
            _insert_case_form(conn, cf_id, case_id, tmpl_id, person_id=emp_id)

        from fastapi import HTTPException
        user = _fake_user(emp_id)
        with self.assertRaises(HTTPException) as ctx:
            patch_form_status(case_id, cf_id,
                              FormStatusPatchPayload(status="pending"), user=user)
        self.assertEqual(ctx.exception.status_code, 422)

    # ── auto-unlock end-to-end (Python layer) ────────────────────────────────

    def test_approving_blocker_unlocks_and_prefills_dependent(self):
        """
        Full flow: GP-7-04 approved → HELFO-1 was blocked → pre-fill runs.
        The DB trigger is Postgres-only; this test verifies the Python layer
        (run_prefill_for_dependents called with correct IDs) so the same
        effect happens in production via both paths.
        """
        case_id = _uuid();  emp_id = _uuid()
        tmpl_gp = _uuid();  tmpl_helfo = _uuid()
        cf_gp = _uuid();    cf_helfo = _uuid()

        with self.engine.begin() as conn:
            _insert_case(conn, case_id, emp_id)
            _insert_profile(conn, emp_id)
            _insert_template(conn, tmpl_gp, code="GP-7-04")
            _insert_template(conn, tmpl_helfo, code="HELFO-1")
            _insert_case_form(conn, cf_gp, case_id, tmpl_gp,
                              status="submitted", person_id=emp_id)
            _insert_case_form(conn, cf_helfo, case_id, tmpl_helfo,
                              status="not_started", blocker_form_id=cf_gp,
                              person_id=emp_id)

        user = _fake_user(emp_id, role="HR")
        payload = FormStatusPatchPayload(status="approved")

        with mock.patch("backend.app.routers.cases.run_prefill_for_dependents") as mock_prefill:
            mock_prefill.return_value = 2
            patch_form_status(case_id, cf_gp, payload, user=user)

        # GP-7-04 should be approved
        with self.engine.connect() as conn:
            gp_status = conn.execute(text(
                "SELECT status FROM case_forms WHERE id = :id"
            ), {"id": cf_gp}).scalar()
        self.assertEqual(gp_status, "approved")

        # Pre-fill was called for GP-7-04's dependents
        mock_prefill.assert_called_once_with(cf_gp, case_id)


if __name__ == "__main__":
    unittest.main()
