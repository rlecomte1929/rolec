"""Deterministic tests for NextActionService."""
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

from backend.services.next_action_service import NextActionService  # noqa: E402


def _fk_pragma(dbapi_connection, _connection_record) -> None:
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SCHEMA = """
CREATE TABLE mobility_cases (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  employee_user_id TEXT NOT NULL,
  origin_country TEXT,
  destination_country TEXT,
  case_type TEXT,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE case_people (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES mobility_cases(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE requirements_catalog (
  id TEXT PRIMARY KEY,
  requirement_code TEXT NOT NULL UNIQUE,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE case_requirement_evaluations (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES mobility_cases(id) ON DELETE CASCADE,
  person_id TEXT,
  requirement_id TEXT NOT NULL REFERENCES requirements_catalog(id) ON DELETE RESTRICT,
  source_rule_id TEXT,
  evaluation_status TEXT NOT NULL,
  reason_text TEXT,
  evaluated_at TEXT,
  evaluated_by TEXT DEFAULT 'system',
  created_at TEXT,
  updated_at TEXT
);
"""


class NextActionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _fk_pragma)
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.svc = NextActionService()

    def test_passport_copy_missing_deterministic_copy(self) -> None:
        case_id = str(uuid.uuid4())
        req_id = str(uuid.uuid4())
        ev_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO mobility_cases (id, company_id, employee_user_id, metadata, created_at, updated_at) "
                    "VALUES (:id, :c, :e, '{}', 't', 't')"
                ),
                {"id": case_id, "c": str(uuid.uuid4()), "e": str(uuid.uuid4())},
            )
            conn.execute(
                text(
                    "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                    "VALUES (:id, 'passport_copy_uploaded', '{}', 't', 't')"
                ),
                {"id": req_id},
            )
            conn.execute(
                text(
                    "INSERT INTO case_requirement_evaluations (id, case_id, requirement_id, evaluation_status, reason_text, created_at, updated_at) "
                    "VALUES (:id, :cid, :rid, 'missing', 'Passport copy has not been uploaded yet.', 't', 't')"
                ),
                {"id": ev_id, "cid": case_id, "rid": req_id},
            )

        with self.engine.connect() as conn:
            out = self.svc.list_actions(conn, case_id)

        self.assertTrue(out["meta"]["case_found"])
        self.assertEqual(out["meta"]["action_count"], 1)
        a = out["actions"][0]
        self.assertEqual(a["id"], ev_id)
        self.assertEqual(a["action_title"], "Upload a valid passport copy")
        self.assertEqual(a["priority"], 1)
        self.assertEqual(a["related_requirement_code"], "passport_copy_uploaded")
        self.assertIn("passport", a["action_description"].lower())

    def test_sort_order_priority_then_title(self) -> None:
        case_id = str(uuid.uuid4())
        r1, r2 = str(uuid.uuid4()), str(uuid.uuid4())
        e1, e2 = str(uuid.uuid4()), str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO mobility_cases (id, company_id, employee_user_id, metadata, created_at, updated_at) "
                    "VALUES (:id, :c, :e, '{}', 't', 't')"
                ),
                {"id": case_id, "c": str(uuid.uuid4()), "e": str(uuid.uuid4())},
            )
            for rid, code in ((r1, "signed_employment_contract"), (r2, "passport_valid")):
                conn.execute(
                    text(
                        "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                        "VALUES (:id, :code, '{}', 't', 't')"
                    ),
                    {"id": rid, "code": code},
                )
            conn.execute(
                text(
                    "INSERT INTO case_requirement_evaluations (id, case_id, requirement_id, evaluation_status, reason_text, created_at, updated_at) "
                    "VALUES (:id, :cid, :rid, 'missing', 'x', 't', 't')"
                ),
                {"id": e1, "cid": case_id, "rid": r1},
            )
            conn.execute(
                text(
                    "INSERT INTO case_requirement_evaluations (id, case_id, requirement_id, evaluation_status, reason_text, created_at, updated_at) "
                    "VALUES (:id, :cid, :rid, 'needs_review', 'y', 't', 't')"
                ),
                {"id": e2, "cid": case_id, "rid": r2},
            )

        with self.engine.connect() as conn:
            out = self.svc.list_actions(conn, case_id)

        titles = [x["action_title"] for x in out["actions"]]
        # passport_valid needs_review -> priority 2; contract missing -> 3
        self.assertEqual(titles[0], "Confirm passport validity")
        self.assertEqual(titles[1], "Add signed employment contract")

    def test_spouse_action_when_metadata_and_no_spouse_person(self) -> None:
        case_id = str(uuid.uuid4())
        emp = str(uuid.uuid4())
        req_id = str(uuid.uuid4())
        ev_id = str(uuid.uuid4())
        meta = json.dumps({"household_includes_spouse": True})
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO mobility_cases (id, company_id, employee_user_id, metadata, created_at, updated_at) "
                    "VALUES (:id, :c, :e, :m, 't', 't')"
                ),
                {"id": case_id, "c": str(uuid.uuid4()), "e": str(uuid.uuid4()), "m": meta},
            )
            conn.execute(
                text(
                    "INSERT INTO case_people (id, case_id, role, created_at, updated_at) VALUES (:id, :cid, 'employee', 't', 't')"
                ),
                {"id": emp, "cid": case_id},
            )
            conn.execute(
                text(
                    "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                    "VALUES (:id, 'proof_of_address', '{}', 't', 't')"
                ),
                {"id": req_id},
            )
            conn.execute(
                text(
                    "INSERT INTO case_requirement_evaluations (id, case_id, requirement_id, evaluation_status, reason_text, created_at, updated_at) "
                    "VALUES (:id, :cid, :rid, 'missing', 'z', 't', 't')"
                ),
                {"id": ev_id, "cid": case_id, "rid": req_id},
            )

        with self.engine.connect() as conn:
            out = self.svc.list_actions(conn, case_id)

        ids = [a["id"] for a in out["actions"]]
        self.assertIn(f"next-household-spouse-{case_id}", ids)
        spouse = next(a for a in out["actions"] if a["id"].startswith("next-household-spouse"))
        self.assertEqual(spouse["action_title"], "Review spouse information")
        self.assertIsNone(spouse["related_requirement_code"])
        self.assertEqual(spouse["priority"], 3)

    def test_not_found_case(self) -> None:
        missing = str(uuid.uuid4())
        with self.engine.connect() as conn:
            out = self.svc.list_actions(conn, missing)
        self.assertFalse(out["meta"]["case_found"])
        self.assertEqual(out["actions"], [])

    def test_invalid_case_id(self) -> None:
        with self.engine.connect() as conn:
            out = self.svc.list_actions(conn, "nope")
        self.assertFalse(out["meta"]["ok"])


if __name__ == "__main__":
    unittest.main()
