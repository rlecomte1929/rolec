"""
[P4-2] HR Dossier Panel — backend tests.

Covers:
  GET  /{case_id}/forms/{form_id}/comments   — list comments
  POST /{case_id}/forms/{form_id}/comments   — create comment
  GET  /{case_id}/forms/{form_id}/events     — history log
  PATCH /{case_id}/forms/{form_id}/flag      — set / clear flag
  PATCH /{case_id}/forms/{form_id}           — extended: rejected + not_started

Pattern: matches existing tests (mock.patch.object on cases_router.main_db,
_assert_case_access patched out, functions called directly).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from typing import Any, Dict
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Pre-import stubs ─────────────────────────────────────────────────────────
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
    "backend.app.services.trigger_engine",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _umock.MagicMock()

# ── Import the router ────────────────────────────────────────────────────────
import backend.app.routers.cases as cases_router  # noqa: E402
from backend.app.routers.cases import (  # noqa: E402
    list_form_comments,
    create_form_comment,
    list_form_events,
    patch_form_flag,
    patch_form_status,
    CommentCreate,
    FlagPatchPayload,
    FormStatusPatchPayload,
)

# ── SQLite in-memory schema ──────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE cases (
    id          TEXT PRIMARY KEY,
    company_id  TEXT,
    employee_id TEXT
);
CREATE TABLE profiles (
    id         TEXT PRIMARY KEY,
    full_name  TEXT,
    email      TEXT,
    role       TEXT DEFAULT 'EMPLOYEE',
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
    fields         TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE case_forms (
    id                TEXT PRIMARY KEY,
    case_id           TEXT NOT NULL,
    form_template_id  TEXT NOT NULL,
    person_id         TEXT,
    dependent_id      TEXT,
    status            TEXT NOT NULL DEFAULT 'not_started',
    completion_pct    INTEGER NOT NULL DEFAULT 0,
    deadline          TEXT,
    deadline_trigger  TEXT,
    blocker_form_id   TEXT,
    is_adhoc          INTEGER NOT NULL DEFAULT 0,
    adhoc_name        TEXT,
    adhoc_authority   TEXT,
    notes             TEXT,
    original_file_url TEXT,
    draft_pdf_url     TEXT,
    submitted_at      TEXT,
    receipt_ref       TEXT,
    flag_note         TEXT,
    flagged_at        TEXT,
    flagged_by        TEXT,
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
CREATE TABLE case_form_comments (
    id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id  TEXT NOT NULL,
    author_id     TEXT NOT NULL,
    content       TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_form_events (
    id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id  TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    actor_id      TEXT,
    from_status   TEXT,
    to_status     TEXT,
    note          TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
"""


def _build_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
            conn.execute(text(stmt))
    return engine


# ── Helpers ──────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())


HR_USER_ID  = _uuid()
EMP_USER_ID = _uuid()

HR_USER:  Dict[str, Any] = {"id": HR_USER_ID,  "sub": HR_USER_ID,  "role": "HR",       "email": "hr@test.com"}
EMP_USER: Dict[str, Any] = {"id": EMP_USER_ID, "sub": EMP_USER_ID, "role": "EMPLOYEE", "email": "emp@test.com"}

COMPANY_ID  = _uuid()
CASE_ID     = _uuid()
TEMPLATE_ID = _uuid()
FORM_ID     = _uuid()


def _seed(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO cases VALUES (:id, :co, :emp)"),
                     {"id": CASE_ID, "co": COMPANY_ID, "emp": EMP_USER_ID})
        conn.execute(text("INSERT INTO profiles VALUES (:id, :name, :email, 'HR', :co)"),
                     {"id": HR_USER_ID, "name": "HR User", "email": "hr@test.com", "co": COMPANY_ID})
        conn.execute(text("INSERT INTO profiles VALUES (:id, :name, :email, 'EMPLOYEE', :co)"),
                     {"id": EMP_USER_ID, "name": "Emp User", "email": "emp@test.com", "co": COMPANY_ID})
        conn.execute(
            text("INSERT INTO form_templates (id, code, name, country, version, fields) "
                 "VALUES (:id, 'UTL-2011', 'Notification of move', 'NO', '1.0.0', :fields)"),
            {"id": TEMPLATE_ID,
             "fields": json.dumps([{"id": "full_name", "label": "Full name",
                                    "type": "text", "required": True, "position": 0}])},
        )
        conn.execute(
            text("INSERT INTO case_forms (id, case_id, form_template_id, status, completion_pct) "
                 "VALUES (:id, :case_id, :tmpl, 'auto_filled', 50)"),
            {"id": FORM_ID, "case_id": CASE_ID, "tmpl": TEMPLATE_ID},
        )


class _FakeMainDB:
    def __init__(self, engine):
        self.engine = engine


# ── Test cases ───────────────────────────────────────────────────────────────

class TestHrDossierPanel(unittest.TestCase):

    def setUp(self):
        self.engine = _build_engine()
        _seed(self.engine)
        self.fake_db = _FakeMainDB(self.engine)

    # ── Comments: list ────────────────────────────────────────────────────────

    def test_list_comments_empty(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = list_form_comments(CASE_ID, FORM_ID, HR_USER)
        self.assertEqual(result, [])

    def test_list_comments_returns_comments(self):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_form_comments (id, case_form_id, author_id, content) "
                     "VALUES (:id, :form_id, :author, 'Check this field')"),
                {"id": _uuid(), "form_id": FORM_ID, "author": HR_USER_ID},
            )
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = list_form_comments(CASE_ID, FORM_ID, HR_USER)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "Check this field")
        self.assertEqual(result[0].author_name, "HR User")

    def test_list_comments_unknown_form_raises_404(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                list_form_comments(CASE_ID, _uuid(), HR_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Comments: create ──────────────────────────────────────────────────────

    def test_create_comment(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = create_form_comment(CASE_ID, FORM_ID, CommentCreate(content="Looks good."), HR_USER)
        self.assertEqual(result.content, "Looks good.")
        self.assertEqual(result.author_id, HR_USER_ID)
        self.assertEqual(result.author_name, "HR User")

    def test_create_comment_empty_raises_422(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                create_form_comment(CASE_ID, FORM_ID, CommentCreate(content="   "), HR_USER)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_create_comment_strips_whitespace(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = create_form_comment(CASE_ID, FORM_ID, CommentCreate(content="  Nice  "), HR_USER)
        self.assertEqual(result.content, "Nice")

    def test_create_comment_unknown_form_raises_404(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                create_form_comment(CASE_ID, _uuid(), CommentCreate(content="x"), HR_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Events: list ──────────────────────────────────────────────────────────

    def test_list_events_empty(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = list_form_events(CASE_ID, FORM_ID, HR_USER)
        self.assertIsInstance(result, list)

    def test_list_events_returns_events(self):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_form_events (id, case_form_id, event_type, actor_id, from_status, to_status) "
                     "VALUES (:id, :form_id, 'status_change', :actor, 'not_started', 'auto_filled')"),
                {"id": _uuid(), "form_id": FORM_ID, "actor": HR_USER_ID},
            )
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = list_form_events(CASE_ID, FORM_ID, HR_USER)
        sc_events = [e for e in result if e.event_type == "status_change"]
        self.assertGreaterEqual(len(sc_events), 1)
        self.assertEqual(sc_events[0].from_status, "not_started")
        self.assertEqual(sc_events[0].actor_name, "HR User")

    def test_list_events_unknown_form_raises_404(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                list_form_events(CASE_ID, _uuid(), HR_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Flag: set ─────────────────────────────────────────────────────────────

    def test_flag_form(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = patch_form_flag(CASE_ID, FORM_ID, FlagPatchPayload(flag_note="Missing doc"), HR_USER)
        self.assertEqual(result.flag_note, "Missing doc")
        self.assertIsNotNone(result.flagged_at)
        self.assertEqual(result.flagged_by, HR_USER_ID)

    def test_flag_writes_flagged_event(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            patch_form_flag(CASE_ID, FORM_ID, FlagPatchPayload(flag_note="Needs review"), HR_USER)
            events = list_form_events(CASE_ID, FORM_ID, HR_USER)
        flagged = [e for e in events if e.event_type == "flagged"]
        self.assertGreaterEqual(len(flagged), 1)
        self.assertEqual(flagged[-1].note, "Needs review")

    def test_clear_flag(self):
        # First set the flag
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            patch_form_flag(CASE_ID, FORM_ID, FlagPatchPayload(flag_note="Set first"), HR_USER)
            # Then clear it
            result = patch_form_flag(CASE_ID, FORM_ID, FlagPatchPayload(flag_note=None), HR_USER)
        self.assertIsNone(result.flag_note)
        self.assertIsNone(result.flagged_at)

    def test_clear_flag_writes_unflagged_event(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            patch_form_flag(CASE_ID, FORM_ID, FlagPatchPayload(flag_note="X"), HR_USER)
            patch_form_flag(CASE_ID, FORM_ID, FlagPatchPayload(flag_note=None), HR_USER)
            events = list_form_events(CASE_ID, FORM_ID, HR_USER)
        self.assertTrue(any(e.event_type == "unflagged" for e in events))

    def test_employee_cannot_flag(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                patch_form_flag(CASE_ID, FORM_ID, FlagPatchPayload(flag_note="fail"), EMP_USER)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_flag_unknown_form_raises_404(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                patch_form_flag(CASE_ID, _uuid(), FlagPatchPayload(flag_note="x"), HR_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Status transitions: HR-only ───────────────────────────────────────────

    def _advance_status(self, to_status: str) -> None:
        """Helper: directly set the DB status so we can test a specific transition."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE case_forms SET status=:s WHERE id=:id"),
                {"s": to_status, "id": FORM_ID},
            )

    def test_hr_can_reject(self):
        self._advance_status("submitted")
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = patch_form_status(
                CASE_ID, FORM_ID,
                FormStatusPatchPayload(status="rejected", note="Apostille missing"),
                HR_USER,
            )
        self.assertEqual(result.status, "rejected")

    def test_hr_can_reset_to_not_started(self):
        self._advance_status("rejected")
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            result = patch_form_status(
                CASE_ID, FORM_ID,
                FormStatusPatchPayload(status="not_started"),
                HR_USER,
            )
        self.assertEqual(result.status, "not_started")

    def test_employee_cannot_reject(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                patch_form_status(
                    CASE_ID, FORM_ID,
                    FormStatusPatchPayload(status="rejected"),
                    EMP_USER,
                )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_employee_cannot_reset_to_not_started(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                patch_form_status(
                    CASE_ID, FORM_ID,
                    FormStatusPatchPayload(status="not_started"),
                    EMP_USER,
                )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unsupported_status_raises_422(self):
        with mock.patch.object(cases_router, "main_db", self.fake_db), \
             mock.patch.object(cases_router, "_assert_case_access", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                patch_form_status(
                    CASE_ID, FORM_ID,
                    FormStatusPatchPayload(status="in_limbo"),
                    HR_USER,
                )
        self.assertEqual(ctx.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
