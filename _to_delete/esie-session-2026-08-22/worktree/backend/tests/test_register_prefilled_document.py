"""
[AIQ-1758] Register a reviewed prefilled data-sheet as a durable case artifact.

Exercises the LIVE wired handler cases_write.register_prefilled_document against
in-memory SQLite with main_db.engine mocked, mirroring test_case_form_documents.py.

Three effects are asserted independently, because they fail independently:
  1. a case_form_documents row with doc_kind='prefilled' + fill_report snapshot,
  2. an audit_logs entry using the prefill convention (event lives in new_value),
  3. the form advancing to 'ready' through the SAME required-field gate the
     status endpoint applies — this must not be a back door around it.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases_write as write_mod  # noqa: E402
from backend.app.routers.cases import RegisterPrefilledPayload  # noqa: E402
from backend.app.routers.cases_write import register_prefilled_document  # noqa: E402

# The column set below mirrors what _load_form_with_template (cases.py) SELECTs —
# a column missing there fails every test with an opaque OperationalError.
# The harness splits this string on the statement separator, so keep SQL comments
# and punctuation out of it.
SCHEMA = """
CREATE TABLE cases (id TEXT PRIMARY KEY, company_id TEXT, employee_id TEXT, hr_owner_id TEXT);
CREATE TABLE profiles (id TEXT PRIMARY KEY, email TEXT, full_name TEXT, company_id TEXT);
CREATE TABLE form_templates (
  id TEXT PRIMARY KEY, code TEXT, name TEXT,
  authority_code TEXT, authority_name TEXT, country TEXT,
  category TEXT, version TEXT, fields TEXT,
  original_pdf_url TEXT, source_url TEXT, verification_status TEXT,
  source_language TEXT
);
CREATE TABLE case_forms (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, form_template_id TEXT,
  status TEXT NOT NULL DEFAULT 'not_started',
  completion_pct INTEGER DEFAULT 0,
  deadline TEXT, deadline_trigger TEXT, blocker_form_id TEXT,
  original_file_url TEXT, draft_pdf_url TEXT,
  submitted_at TEXT, receipt_ref TEXT, rejection_reason TEXT,
  person_id TEXT, dependent_id TEXT,
  is_adhoc INTEGER DEFAULT 0, adhoc_name TEXT, adhoc_authority TEXT, notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT
);
CREATE TABLE case_form_field_values (
  case_form_id TEXT NOT NULL, field_id TEXT NOT NULL, value TEXT, source TEXT
);
CREATE TABLE case_form_documents (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  case_form_id TEXT NOT NULL, case_id TEXT NOT NULL,
  file_name TEXT NOT NULL, storage_path TEXT NOT NULL,
  content_type TEXT, size_bytes INTEGER, uploaded_by TEXT, doc_key TEXT,
  doc_kind TEXT, fill_report TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  entity_type TEXT, entity_id TEXT, action_type TEXT, actor_type TEXT,
  actor_id TEXT, old_value_json TEXT, new_value_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_FIELDS = [
    {"id": "legal_last_name", "label": "Family name", "required": True, "position": 0},
    {"id": "middle_name", "label": "Middle name", "required": False, "position": 1},
]


def _u() -> str:
    return str(uuid.uuid4())


def _emp(uid: str) -> dict:
    return {"id": uid, "role": "EMPLOYEE", "is_admin": False}


class RegisterPrefilledTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))

        p = mock.patch.object(write_mod.main_db, "engine", self.engine)
        p.start()
        self.addCleanup(p.stop)

        self.company_id, self.employee_id = _u(), _u()
        self.case_id, self.form_id, self.tpl_id = _u(), _u(), _u()
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, email, full_name, company_id) VALUES (:i,:e,:n,:c)"),
                {"i": self.employee_id, "e": "e@x.com", "n": "Marc", "c": self.company_id},
            )
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id) VALUES (:i,:c,:e)"),
                {"i": self.case_id, "c": self.company_id, "e": self.employee_id},
            )
            conn.execute(
                text("INSERT INTO form_templates (id, name, fields) VALUES (:i,:n,:f)"),
                {"i": self.tpl_id, "n": "FR-NO Data Sheet", "f": json.dumps(_FIELDS)},
            )
            conn.execute(
                text("INSERT INTO case_forms (id, case_id, form_template_id) VALUES (:i,:c,:t)"),
                {"i": self.form_id, "c": self.case_id, "t": self.tpl_id},
            )

    def _fill_required(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_form_field_values (case_form_id, field_id, value, source) "
                     "VALUES (:f,:k,:v,:s)"),
                {"f": self.form_id, "k": "legal_last_name", "v": "Dubois", "s": "intake_profile"},
            )

    def _register(self, **kw):
        payload = RegisterPrefilledPayload(**kw)
        return register_prefilled_document(
            case_id=self.case_id, form_id=self.form_id,
            payload=payload, user=_emp(self.employee_id),
        )

    # ── 1. the document row ──────────────────────────────────────────────────

    def test_creates_prefilled_document_row_with_fill_report(self) -> None:
        self._fill_required()
        report = {"filled": 1, "total": 2, "sources": {"legal_last_name": "intake_profile"}}
        item = self._register(fill_report=report)

        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT doc_kind, fill_report, storage_path, case_id, case_form_id, "
                     "content_type FROM case_form_documents WHERE id = :i"),
                {"i": item.id},
            ).mappings().first()

        self.assertIsNotNone(row)
        self.assertEqual(row["doc_kind"], "prefilled")
        self.assertEqual(json.loads(row["fill_report"]), report)
        self.assertEqual(row["case_id"], self.case_id)
        self.assertEqual(row["case_form_id"], self.form_id)
        self.assertEqual(row["content_type"], "application/pdf")
        # Versioned path so re-registering never overwrites the prior artifact.
        self.assertIn(f"case-forms/{self.form_id}/prefilled/", row["storage_path"])

    def test_reregistering_creates_a_new_version_not_an_overwrite(self) -> None:
        self._fill_required()
        first = self._register(fill_report={"v": 1})
        second = self._register(fill_report={"v": 2})
        self.assertNotEqual(first.id, second.id)

        with self.engine.begin() as conn:
            n = conn.execute(
                text("SELECT count(*) AS n FROM case_form_documents "
                     "WHERE case_form_id = :f AND doc_kind = 'prefilled'"),
                {"f": self.form_id},
            ).mappings().first()["n"]
        self.assertEqual(n, 2)

    # ── 2. the audit trail ───────────────────────────────────────────────────

    def test_writes_audit_row_using_the_prefill_convention(self) -> None:
        self._fill_required()
        item = self._register()

        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT entity_type, entity_id, action_type, new_value_json FROM audit_logs "
                     "WHERE entity_id = :f ORDER BY created_at DESC"),
                {"f": self.form_id},
            ).mappings().first()

        self.assertIsNotNone(row, "no audit row written")
        self.assertEqual(row["entity_type"], "case_form")
        self.assertEqual(row["entity_id"], self.form_id)
        # action_type is CHECK-constrained to insert/update/delete in PG — the
        # semantic event must live in new_value_json, not a bespoke action_type.
        self.assertEqual(row["action_type"], "insert")
        payload = json.loads(row["new_value_json"])
        self.assertEqual(payload["event"], "prefill")
        self.assertEqual(payload["doc_kind"], "prefilled")
        self.assertEqual(payload["document_id"], item.id)

    # ── 3. the status advance + its gate ─────────────────────────────────────

    def test_advances_status_to_ready(self) -> None:
        self._fill_required()
        self._register()
        with self.engine.begin() as conn:
            status = conn.execute(
                text("SELECT status FROM case_forms WHERE id = :i"), {"i": self.form_id}
            ).mappings().first()["status"]
        self.assertEqual(status, "ready")

    def test_missing_required_fields_blocks_registration(self) -> None:
        # No values inserted — the same gate PATCH /status {'ready'} applies must
        # reject this, so registering cannot be a back door around it.
        with self.assertRaises(HTTPException) as ctx:
            self._register()
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("legal_last_name", str(ctx.exception.detail))

        with self.engine.begin() as conn:
            n = conn.execute(
                text("SELECT count(*) AS n FROM case_form_documents"),
            ).mappings().first()["n"]
        self.assertEqual(n, 0, "document row must not survive the failed transaction")

    def test_advance_status_false_registers_without_moving_lifecycle(self) -> None:
        # Re-registering a corrected artifact on an already-advanced form must not
        # require the required-field gate to be re-satisfied.
        item = self._register(advance_status=False)
        self.assertIsNotNone(item.id)
        with self.engine.begin() as conn:
            status = conn.execute(
                text("SELECT status FROM case_forms WHERE id = :i"), {"i": self.form_id}
            ).mappings().first()["status"]
        self.assertEqual(status, "not_started")

    # ── guards ───────────────────────────────────────────────────────────────

    def test_unknown_form_is_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            register_prefilled_document(
                case_id=self.case_id, form_id=_u(),
                payload=RegisterPrefilledPayload(), user=_emp(self.employee_id),
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_audit_failure_does_not_break_registration(self) -> None:
        # The audit is best-effort and outside the write transaction, matching
        # prefill_engine._insert_prefill_audit: losing the audit must not lose
        # the document.
        self._fill_required()
        with mock.patch.object(write_mod, "insert_audit_log", side_effect=RuntimeError("boom")):
            item = self._register()
        self.assertIsNotNone(item.id)
        with self.engine.begin() as conn:
            n = conn.execute(
                text("SELECT count(*) AS n FROM case_form_documents WHERE id = :i"),
                {"i": item.id},
            ).mappings().first()["n"]
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
