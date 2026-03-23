"""Controlled admin evaluation trigger: assignment_id -> mobility case -> evaluator + next actions."""
from __future__ import annotations

import os
import sys
import unittest
import uuid

from sqlalchemy import create_engine, event, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
from backend.database import Database
from backend.services.admin_assignment_evaluation_trigger import run_evaluation_for_assignment
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


class AdminAssignmentEvaluationTriggerTests(unittest.TestCase):
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
        self.db = Database()

    def tearDown(self) -> None:
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def test_assignment_backed_evaluation_runs(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)
            conn.execute(
                text(
                    "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                    "VALUES (:id, :aid, :mid, 't', 't')"
                ),
                {"id": str(uuid.uuid4()), "aid": aid, "mid": case_id},
            )

        out = run_evaluation_for_assignment(self.db, aid)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out["assignment_id"], aid)
        self.assertEqual(out["mobility_case_id"], case_id)
        self.assertGreaterEqual(out.get("evaluated_count", 0), 1)
        self.assertIn("status_counts", out)
        self.assertIn("next_actions_preview", out)

    def test_missing_mobility_link(self) -> None:
        out = run_evaluation_for_assignment(self.db, str(uuid.uuid4()))
        self.assertFalse(out.get("ok"))
        self.assertEqual((out.get("error") or {}).get("code"), "no_mobility_link")

    def test_passport_copy_document_met_when_seeded(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)
            conn.execute(
                text(
                    "INSERT INTO case_documents (id, case_id, person_id, document_key, document_status, metadata, created_at, updated_at) "
                    "VALUES (:id, :cid, :pid, 'passport_copy', 'uploaded', '{}', 't1', 't1')"
                ),
                {"id": str(uuid.uuid4()), "cid": case_id, "pid": emp_id},
            )
            conn.execute(
                text(
                    "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                    "VALUES (:id, :aid, :mid, 't', 't')"
                ),
                {"id": str(uuid.uuid4()), "aid": aid, "mid": case_id},
            )

        out = run_evaluation_for_assignment(self.db, aid)
        self.assertTrue(out.get("ok"))
        by_code = {r["requirement_code"]: r for r in out["results"]}
        self.assertEqual(by_code.get("passport_copy_uploaded", {}).get("evaluation_status"), "met")

    def test_bridge_unaffected_after_evaluation(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)
            conn.execute(
                text(
                    "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                    "VALUES (:id, :aid, :mid, 't', 't')"
                ),
                {"id": str(uuid.uuid4()), "aid": aid, "mid": case_id},
            )
        with self.engine.connect() as conn:
            n_links = conn.execute(text("SELECT COUNT(*) FROM assignment_mobility_links")).scalar()
            n_people = conn.execute(text("SELECT COUNT(*) FROM case_people WHERE case_id = :c"), {"c": case_id}).scalar()
        run_evaluation_for_assignment(self.db, aid)
        with self.engine.connect() as conn:
            self.assertEqual(
                conn.execute(text("SELECT COUNT(*) FROM assignment_mobility_links")).scalar(),
                n_links,
            )
            self.assertEqual(
                conn.execute(text("SELECT COUNT(*) FROM case_people WHERE case_id = :c"), {"c": case_id}).scalar(),
                n_people,
            )

    def test_next_actions_from_evaluations(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)
            conn.execute(
                text(
                    "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                    "VALUES (:id, :aid, :mid, 't', 't')"
                ),
                {"id": str(uuid.uuid4()), "aid": aid, "mid": case_id},
            )

        out = run_evaluation_for_assignment(self.db, aid)
        self.assertTrue(out.get("ok"))
        actions = (out.get("next_actions_preview") or {}).get("actions") or []
        codes = {a.get("related_requirement_code") for a in actions}
        self.assertTrue(codes & {"passport_copy_uploaded", "passport_valid", "signed_employment_contract"})


if __name__ == "__main__":
    unittest.main()
