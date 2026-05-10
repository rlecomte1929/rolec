"""Admin mobility inspect operational payload (readiness + snapshots + next actions preview)."""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid

from sqlalchemy import create_engine, event, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
from backend.services.case_context_service import CaseContextService
from backend.services.mobility_inspect_service import build_mobility_operational_inspect
from backend.tests.test_requirement_evaluation_service import (  # noqa: E402
    MOBILITY_SCHEMA,
    _fk_pragma,
    _seed_fr_no_pilot,
)

LINK_DDL = """
CREATE TABLE assignment_mobility_links (
  id TEXT PRIMARY KEY,
  assignment_id TEXT NOT NULL UNIQUE,
  mobility_case_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (mobility_case_id) REFERENCES mobility_cases(id) ON DELETE CASCADE
);
"""


class AdminMobilityInspectOperationalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _fk_pragma)
        with self.engine.begin() as conn:
            for stmt in MOBILITY_SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
            for stmt in LINK_DDL.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self._prev_engine = dbmod._engine
        self._prev_sqlite = dbmod._is_sqlite
        dbmod._engine = self.engine
        dbmod._is_sqlite = True

    def tearDown(self) -> None:
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def test_operational_reflects_bridge_passport_and_evaluations(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)
            conn.execute(
                text(
                    "INSERT INTO case_documents (id, case_id, person_id, document_key, document_status, metadata, created_at, updated_at) "
                    "VALUES (:id, :cid, :pid, 'passport_copy', 'uploaded', :meta, 't1', 't1')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "cid": case_id,
                    "pid": emp_id,
                    "meta": json.dumps(
                        {"case_evidence_id": "ev-test-1", "submitted_at": "2024-06-01T12:00:00Z"}
                    ),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                    "VALUES (:id, :aid, :mid, 't', 't')"
                ),
                {"id": str(uuid.uuid4()), "aid": aid, "mid": case_id},
            )

        with self.engine.connect() as conn:
            ctx = CaseContextService().fetch(conn, case_id)
            op = build_mobility_operational_inspect(conn, case_id, ctx)

        self.assertEqual(op["assignment_id"], aid)
        self.assertEqual(op["mobility_case_id"], case_id)
        self.assertEqual(op["bridge_status"], "linked")
        rf = op["readiness_flags"]
        self.assertTrue(rf["has_mobility_link"])
        self.assertTrue(rf["has_employee_person"])
        self.assertTrue(rf["has_passport_document"])
        self.assertFalse(rf["has_evaluations"])

        ps = op["passport_document_snapshot"]
        self.assertEqual(ps.get("document_key"), "passport_copy")
        self.assertEqual(ps.get("source_evidence_id"), "ev-test-1")
        self.assertEqual(ps.get("submitted_at"), "2024-06-01T12:00:00Z")

        self.assertIn("actions", op["next_actions_preview"])

    def test_operational_no_bridge(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)

        with self.engine.connect() as conn:
            ctx = CaseContextService().fetch(conn, case_id)
            op = build_mobility_operational_inspect(conn, case_id, ctx)

        self.assertIsNone(op["assignment_id"])
        self.assertEqual(op["bridge_status"], "missing")
        self.assertFalse(op["readiness_flags"]["has_mobility_link"])

    def test_employee_snapshot_from_metadata(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        meta = {"full_name": "Jane Q", "email": "j@ex.com", "nationality": "FR"}
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)
            conn.execute(
                text("UPDATE case_people SET metadata = :m WHERE id = :id"),
                {"m": json.dumps(meta), "id": emp_id},
            )

        with self.engine.connect() as conn:
            ctx = CaseContextService().fetch(conn, case_id)
            op = build_mobility_operational_inspect(conn, case_id, ctx)

        es = op["employee_snapshot"]
        self.assertEqual(es.get("full_name"), "Jane Q")
        self.assertEqual(es.get("email"), "j@ex.com")
        self.assertEqual(es.get("nationality"), "FR")


if __name__ == "__main__":
    unittest.main()
