"""
[AIQ-1758] Tests for prefilled_document_service.register_prefilled_document.

Same harness as test_prefill_engine: an in-memory SQLite DB mirroring only the
tables the service reads/writes, with prefilled_document_service.db.engine
patched per test.
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

from backend.app.services import prefilled_document_service as svc  # noqa: E402
from backend.app.services.prefilled_document_service import (  # noqa: E402
    register_prefilled_document,
)


SCHEMA = """
CREATE TABLE cases (
    id TEXT PRIMARY KEY
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
    status           TEXT NOT NULL DEFAULT 'auto_filled',
    updated_at       TEXT DEFAULT (datetime('now'))
);
CREATE TABLE case_form_field_values (
    id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    case_form_id TEXT NOT NULL,
    field_id     TEXT NOT NULL,
    value        TEXT,
    filled_by    TEXT,
    ai_confidence REAL,
    source       TEXT,
    reviewed     INTEGER NOT NULL DEFAULT 0,
    overridden   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (case_form_id, field_id)
);
CREATE TABLE case_form_documents (
    id           TEXT PRIMARY KEY,
    case_form_id TEXT NOT NULL,
    case_id      TEXT NOT NULL,
    file_name    TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    content_type TEXT,
    size_bytes   INTEGER,
    uploaded_by  TEXT,
    doc_kind     TEXT,
    fill_report  TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
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

# A data-sheet-shaped template: a filled field, an unsourced (blank) field, and a
# consult-professional determination.
FIELDS = [
    {"id": "full_name", "label": "Full legal name", "prefill_source": "profile.legal_full_name"},
    {"id": "arrival_date", "label": "Date of arrival in Norway"},  # no source → blank
    {"id": "tax_residency_status", "label": "Tax-residency status", "consult_professional": True},
]


def _uuid() -> str:
    return str(uuid.uuid4())


class RegisterPrefilledDocumentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.patcher = mock.patch.object(svc.db, "engine", self.engine)
        self.patcher.start()

        self.case_id = _uuid()
        self.cf_id = _uuid()
        self.tmpl = _uuid()
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO cases (id) VALUES (:id)"), {"id": self.case_id})
            conn.execute(
                text("INSERT INTO form_templates (id, code, fields) VALUES (:id, :c, :f)"),
                {"id": self.tmpl, "c": "RP-NO-DATASHEET", "f": json.dumps(FIELDS)},
            )
            conn.execute(
                text(
                    "INSERT INTO case_forms (id, case_id, form_template_id, status) "
                    "VALUES (:id, :cid, :tid, 'auto_filled')"
                ),
                {"id": self.cf_id, "cid": self.case_id, "tid": self.tmpl},
            )
            conn.execute(
                text(
                    "INSERT INTO case_form_field_values "
                    "(id, case_form_id, field_id, value, filled_by, source, reviewed) "
                    "VALUES (:id, :cf, 'full_name', 'Sophie Leblanc', 'system', 'intake_profile', 1)"
                ),
                {"id": _uuid(), "cf": self.cf_id},
            )

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()

    def _doc_row(self):
        with self.engine.connect() as conn:
            return conn.execute(
                text("SELECT * FROM case_form_documents WHERE case_form_id = :cf"),
                {"cf": self.cf_id},
            ).mappings().first()

    # ── happy path ───────────────────────────────────────────────────────────

    def test_registers_document_audit_and_advances_status(self):
        result = register_prefilled_document(self.case_id, self.cf_id, actor_id=_uuid())

        # 1. case_form_documents row
        doc = self._doc_row()
        self.assertIsNotNone(doc)
        self.assertEqual(doc["doc_kind"], "prefilled")
        self.assertTrue(doc["storage_path"].startswith(f"{self.case_id}/prefilled/{self.cf_id}/"))
        self.assertEqual(doc["content_type"], "application/json")
        self.assertEqual(doc["id"], result["document_id"])

        # fill_report snapshot: one entry per field, correct statuses, NO raw value column
        report = json.loads(doc["fill_report"])
        by_id = {r["field_id"]: r for r in report}
        self.assertEqual(by_id["full_name"]["status"], "filled")
        self.assertEqual(by_id["full_name"]["source"], "intake_profile")
        self.assertEqual(by_id["arrival_date"]["status"], "blank_missing_data")
        self.assertEqual(by_id["tax_residency_status"]["status"], "consult")
        for r in report:
            self.assertNotIn("value", r)  # values never duplicated into the column

        # 2. audit_logs entry (prefill convention)
        with self.engine.connect() as conn:
            audit = conn.execute(
                text("SELECT * FROM audit_logs WHERE entity_id = :id"),
                {"id": self.cf_id},
            ).mappings().first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit["entity_type"], "case_form")
        self.assertEqual(audit["action_type"], "insert")
        payload = json.loads(audit["new_value_json"])
        self.assertEqual(payload["event"], "prefill")
        self.assertEqual(payload["kind"], "register")

        # 3. status advanced per the state machine
        self.assertEqual(result["status"], "ready")
        with self.engine.connect() as conn:
            status = conn.execute(
                text("SELECT status FROM case_forms WHERE id = :id"), {"id": self.cf_id}
            ).scalar()
        self.assertEqual(status, "ready")

    # ── guarded advance ───────────────────────────────────────────────────────

    def test_does_not_downgrade_a_submitted_form(self):
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE case_forms SET status = 'submitted' WHERE id = :id"),
                {"id": self.cf_id},
            )
        result = register_prefilled_document(self.case_id, self.cf_id)
        # Document is still registered, but status is NOT downgraded to 'ready'.
        self.assertIsNotNone(self._doc_row())
        self.assertEqual(result["status"], "submitted")

    # ── validation / errors ───────────────────────────────────────────────────

    def test_unknown_form_raises_value_error(self):
        with self.assertRaises(ValueError):
            register_prefilled_document(self.case_id, "does-not-exist")

    def test_non_uuid_actor_is_dropped(self):
        register_prefilled_document(self.case_id, self.cf_id, actor_id="legacy-42")
        doc = self._doc_row()
        self.assertIsNone(doc["uploaded_by"])  # non-uuid → nullable, not a bad cast


if __name__ == "__main__":
    unittest.main()
