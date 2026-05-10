"""Tests for RequirementEvaluationService (deterministic MVP evaluator)."""
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

from backend.services.requirement_evaluation_service import RequirementEvaluationService  # noqa: E402


def _fk_pragma(dbapi_connection, _connection_record) -> None:
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


MOBILITY_SCHEMA = """
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
CREATE TABLE case_documents (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES mobility_cases(id) ON DELETE CASCADE,
  person_id TEXT REFERENCES case_people(id) ON DELETE SET NULL,
  document_key TEXT,
  document_status TEXT NOT NULL DEFAULT 'missing',
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
CREATE TABLE policy_rules (
  id TEXT PRIMARY KEY,
  rule_code TEXT NOT NULL UNIQUE,
  conditions TEXT NOT NULL DEFAULT '{}',
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE case_requirement_evaluations (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES mobility_cases(id) ON DELETE CASCADE,
  person_id TEXT REFERENCES case_people(id) ON DELETE SET NULL,
  requirement_id TEXT NOT NULL REFERENCES requirements_catalog(id) ON DELETE RESTRICT,
  source_rule_id TEXT REFERENCES policy_rules(id) ON DELETE SET NULL,
  evaluation_status TEXT NOT NULL DEFAULT 'unknown',
  reason_text TEXT,
  evaluated_at TEXT,
  evaluated_by TEXT DEFAULT 'system',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  old_value_json TEXT,
  new_value_json TEXT,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT
);
"""


def _seed_fr_no_pilot(conn, case_id: str, employee_id: str, with_passport: bool, with_contract: bool) -> tuple:
    """Returns (rule_id, req_passport_valid, req_pass_copy, req_contract)."""
    req_pv = str(uuid.uuid4())
    req_pc = str(uuid.uuid4())
    req_ct = str(uuid.uuid4())
    rule_id = str(uuid.uuid4())

    conn.execute(
        text(
            """
            INSERT INTO mobility_cases (id, company_id, employee_user_id, origin_country,
              destination_country, case_type, metadata, created_at, updated_at)
            VALUES (:id, :co, :eu, 'FR', 'NO', 'work_relocation', '{}', 't1', 't1')
            """
        ),
        {"id": case_id, "co": str(uuid.uuid4()), "eu": str(uuid.uuid4())},
    )
    conn.execute(
        text(
            "INSERT INTO case_people (id, case_id, role, created_at, updated_at) "
            "VALUES (:id, :cid, 'employee', 't1', 't1')"
        ),
        {"id": employee_id, "cid": case_id},
    )
    for rid, code in ((req_pv, "passport_valid"), (req_pc, "passport_copy_uploaded"), (req_ct, "signed_employment_contract")):
        conn.execute(
            text(
                "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                "VALUES (:id, :c, '{}', 't1', 't1')"
            ),
            {"id": rid, "c": code},
        )
    cond = {
        "match": {"origin_country": "FR", "destination_country": "NO", "case_type": "work_relocation"},
        "applies_to_roles": ["employee"],
        "requires_requirement_codes": ["passport_valid", "passport_copy_uploaded", "signed_employment_contract"],
    }
    conn.execute(
        text(
            "INSERT INTO policy_rules (id, rule_code, conditions, metadata, created_at, updated_at) "
            "VALUES (:id, 'pilot_core', :c, '{}', 't1', 't1')"
        ),
        {"id": rule_id, "c": json.dumps(cond)},
    )
    if with_passport:
        conn.execute(
            text(
                "INSERT INTO case_documents (id, case_id, person_id, document_key, document_status, created_at, updated_at) "
                "VALUES (:id, :cid, :pid, 'passport_scan.pdf', 'uploaded', 't1', 't1')"
            ),
            {"id": str(uuid.uuid4()), "cid": case_id, "pid": employee_id},
        )
    if with_contract:
        conn.execute(
            text(
                "INSERT INTO case_documents (id, case_id, person_id, document_key, document_status, created_at, updated_at) "
                "VALUES (:id, :cid, :pid, 'employment_contract.pdf', 'approved', 't1', 't1')"
            ),
            {"id": str(uuid.uuid4()), "cid": case_id, "pid": employee_id},
        )
    return rule_id, req_pv, req_pc, req_ct


class RequirementEvaluationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _fk_pragma)
        with self.engine.begin() as conn:
            for stmt in MOBILITY_SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.svc = RequirementEvaluationService()

    def test_matching_route_passport_and_contract_states(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=True, with_contract=True)

        with self.engine.begin() as conn:
            out = self.svc.evaluate_case(conn, case_id)

        self.assertIsNone(out.get("error"))
        self.assertEqual(out["meta"]["evaluated_count"], 3)
        by_code = {r["requirement_code"]: r for r in out["results"]}
        self.assertEqual(by_code["passport_copy_uploaded"]["evaluation_status"], "met")
        self.assertEqual(by_code["passport_valid"]["evaluation_status"], "needs_review")
        self.assertIn("not checked automatically", by_code["passport_valid"]["reason_text"].lower())
        self.assertEqual(by_code["signed_employment_contract"]["evaluation_status"], "met")

        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT requirement_id, evaluation_status, reason_text, evaluated_by FROM case_requirement_evaluations WHERE case_id = :c"),
                {"c": case_id},
            ).mappings().all()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["evaluated_by"] == "system" for r in rows))

    def test_missing_passport(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)

        with self.engine.begin() as conn:
            out = self.svc.evaluate_case(conn, case_id)

        by_code = {r["requirement_code"]: r for r in out["results"]}
        self.assertEqual(by_code["passport_copy_uploaded"]["evaluation_status"], "missing")
        self.assertEqual(by_code["passport_valid"]["evaluation_status"], "missing")
        self.assertIn("found", by_code["passport_valid"]["reason_text"].lower())

    def test_contract_present_only(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=True)

        with self.engine.begin() as conn:
            out = self.svc.evaluate_case(conn, case_id)

        by_code = {r["requirement_code"]: r for r in out["results"]}
        self.assertEqual(by_code["signed_employment_contract"]["evaluation_status"], "met")
        self.assertEqual(by_code["passport_copy_uploaded"]["evaluation_status"], "missing")

    def test_rule_not_applicable_wrong_route(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO mobility_cases (id, company_id, employee_user_id, origin_country,
                      destination_country, case_type, metadata, created_at, updated_at)
                    VALUES (:id, :co, :eu, 'DE', 'SE', 'work_relocation', '{}', 't1', 't1')
                    """
                ),
                {"id": case_id, "co": str(uuid.uuid4()), "eu": str(uuid.uuid4())},
            )
            conn.execute(
                text(
                    "INSERT INTO case_people (id, case_id, role, created_at, updated_at) "
                    "VALUES (:id, :cid, 'employee', 't1', 't1')"
                ),
                {"id": emp_id, "cid": case_id},
            )
            req_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                    "VALUES (:id, 'passport_valid', '{}', 't1', 't1')"
                ),
                {"id": req_id},
            )
            cond = {
                "match": {"origin_country": "FR", "destination_country": "NO", "case_type": "work_relocation"},
                "applies_to_roles": ["employee"],
                "requires_requirement_codes": ["passport_valid"],
            }
            conn.execute(
                text(
                    "INSERT INTO policy_rules (id, rule_code, conditions, metadata, created_at, updated_at) "
                    "VALUES (:id, 'only_fr_no', :c, '{}', 't1', 't1')"
                ),
                {"id": str(uuid.uuid4()), "c": json.dumps(cond)},
            )

        with self.engine.begin() as conn:
            out = self.svc.evaluate_case(conn, case_id)

        self.assertEqual(out["meta"]["evaluated_count"], 0)
        self.assertEqual(out["results"], [])

    def test_evaluation_write_inserts_audit_logs(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=False, with_contract=False)

        with self.engine.begin() as conn:
            self.svc.evaluate_case(conn, case_id)

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT count(*) AS c FROM audit_logs WHERE entity_type = 'case_requirement_evaluations'"
                )
            ).mappings().first()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["c"], 3)

    def test_upsert_same_row_on_second_run(self) -> None:
        case_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            _seed_fr_no_pilot(conn, case_id, emp_id, with_passport=True, with_contract=False)

        with self.engine.begin() as conn:
            out1 = self.svc.evaluate_case(conn, case_id)
        id1 = {r["requirement_code"]: r["evaluation_id"] for r in out1["results"]}

        with self.engine.begin() as conn:
            out2 = self.svc.evaluate_case(conn, case_id)
        id2 = {r["requirement_code"]: r["evaluation_id"] for r in out2["results"]}

        self.assertEqual(id1, id2)


if __name__ == "__main__":
    unittest.main()
