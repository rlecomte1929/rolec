"""Unit tests for CaseContextService (mobility graph context)."""
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

from backend.services.case_context_service import CaseContextService  # noqa: E402


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
"""


class CaseContextServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _fk_pragma)
        with self.engine.begin() as conn:
            for stmt in MOBILITY_SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.svc = CaseContextService()

    def test_valid_case_full_data(self) -> None:
        case_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0001"
        emp_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0011"
        spouse_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0012"
        doc_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0021"
        req_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0031"
        req_b = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0032"
        rule_emp = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0041"
        rule_spouse = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0042"
        ev_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0051"
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO mobility_cases (id, company_id, employee_user_id, origin_country,
                      destination_country, case_type, metadata, created_at, updated_at)
                    VALUES (:id, :co, :eu, 'FR', 'NO', 'work_relocation', :meta, 't1', 't1')
                    """
                ),
                {
                    "id": case_id,
                    "co": str(uuid.uuid4()),
                    "eu": str(uuid.uuid4()),
                    "meta": json.dumps({"needs_proof_of_address": False}),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO case_people (id, case_id, role, created_at, updated_at) "
                    "VALUES (:id, :cid, :role, 't1', 't1')"
                ),
                {"id": emp_id, "cid": case_id, "role": "employee"},
            )
            conn.execute(
                text(
                    "INSERT INTO case_people (id, case_id, role, created_at, updated_at) "
                    "VALUES (:id, :cid, :role, 't2', 't2')"
                ),
                {"id": spouse_id, "cid": case_id, "role": "spouse_partner"},
            )
            conn.execute(
                text(
                    "INSERT INTO case_documents (id, case_id, person_id, document_key, document_status, created_at, updated_at) "
                    "VALUES (:id, :cid, :pid, 'passport_copy', 'uploaded', 't1', 't1')"
                ),
                {"id": doc_id, "cid": case_id, "pid": emp_id},
            )
            conn.execute(
                text(
                    "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                    "VALUES (:id, :code, '{}', 't1', 't1')"
                ),
                {"id": req_a, "code": "req_alpha"},
            )
            conn.execute(
                text(
                    "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                    "VALUES (:id, :code, '{}', 't1', 't1')"
                ),
                {"id": req_b, "code": "req_beta"},
            )
            cond_emp = {
                "match": {"origin_country": "FR", "destination_country": "NO", "case_type": "work_relocation"},
                "applies_to_roles": ["employee"],
                "requires_requirement_codes": ["req_alpha"],
            }
            cond_spouse = {
                "match": {"origin_country": "FR", "destination_country": "NO", "case_type": "work_relocation"},
                "applies_to_roles": ["spouse_partner"],
                "requires_requirement_codes": ["req_beta"],
            }
            conn.execute(
                text(
                    "INSERT INTO policy_rules (id, rule_code, conditions, metadata, created_at, updated_at) "
                    "VALUES (:id, :code, :cond, '{}', 't1', 't1')"
                ),
                {"id": rule_emp, "code": "rule_employee", "cond": json.dumps(cond_emp)},
            )
            conn.execute(
                text(
                    "INSERT INTO policy_rules (id, rule_code, conditions, metadata, created_at, updated_at) "
                    "VALUES (:id, :code, :cond, '{}', 't1', 't1')"
                ),
                {"id": rule_spouse, "code": "rule_spouse", "cond": json.dumps(cond_spouse)},
            )
            conn.execute(
                text(
                    "INSERT INTO case_requirement_evaluations (id, case_id, person_id, requirement_id, "
                    "source_rule_id, evaluation_status, created_at, updated_at) "
                    "VALUES (:id, :cid, :pid, :rid, :srid, 'pending', 't1', 't1')"
                ),
                {
                    "id": ev_id,
                    "cid": case_id,
                    "pid": emp_id,
                    "rid": req_a,
                    "srid": rule_emp,
                },
            )

        with self.engine.connect() as conn:
            ctx = self.svc.fetch(conn, case_id)

        self.assertTrue(ctx["meta"]["ok"])
        self.assertTrue(ctx["meta"]["case_found"])
        self.assertIsNotNone(ctx["case"])
        self.assertEqual(ctx["case"]["origin_country"], "FR")
        self.assertEqual(len(ctx["people"]), 2)
        self.assertEqual(len(ctx["documents"]), 1)
        self.assertEqual(ctx["documents"][0]["document_key"], "passport_copy")
        codes = {r["rule_code"] for r in ctx["applicable_rules"]}
        self.assertEqual(codes, {"rule_employee", "rule_spouse"})
        req_codes = {r["requirement_code"] for r in ctx["requirements"]}
        self.assertEqual(req_codes, {"req_alpha", "req_beta"})
        self.assertEqual(len(ctx["evaluations"]), 1)
        self.assertEqual(ctx["evaluations"][0]["requirement_code"], "req_alpha")

    def test_valid_case_no_documents(self) -> None:
        case_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbb001"
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
                {"id": str(uuid.uuid4()), "cid": case_id},
            )
        with self.engine.connect() as conn:
            ctx = self.svc.fetch(conn, case_id)
        self.assertTrue(ctx["meta"]["case_found"])
        self.assertEqual(ctx["documents"], [])

    def test_spouse_missing_excludes_spouse_only_rule(self) -> None:
        case_id = "cccccccc-cccc-4ccc-8ccc-cccccccc0001"
        req_spouse = "cccccccc-cccc-4ccc-8ccc-cccccccc0031"
        req_emp = "cccccccc-cccc-4ccc-8ccc-cccccccc0032"
        rule_spouse_only = "cccccccc-cccc-4ccc-8ccc-cccccccc0041"
        rule_employee = "cccccccc-cccc-4ccc-8ccc-cccccccc0042"
        with self.engine.begin() as conn:
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
                {"id": str(uuid.uuid4()), "cid": case_id},
            )
            conn.execute(
                text(
                    "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                    "VALUES (:id, 'spouse_req', '{}', 't1', 't1')"
                ),
                {"id": req_spouse},
            )
            conn.execute(
                text(
                    "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                    "VALUES (:id, 'emp_req', '{}', 't1', 't1')"
                ),
                {"id": req_emp},
            )
            cond_spouse = {
                "match": {"origin_country": "FR", "destination_country": "NO", "case_type": "work_relocation"},
                "applies_to_roles": ["spouse_partner"],
                "requires_requirement_codes": ["spouse_req"],
            }
            cond_emp = {
                "match": {"origin_country": "FR", "destination_country": "NO", "case_type": "work_relocation"},
                "applies_to_roles": ["employee"],
                "requires_requirement_codes": ["emp_req"],
            }
            conn.execute(
                text(
                    "INSERT INTO policy_rules (id, rule_code, conditions, metadata, created_at, updated_at) "
                    "VALUES (:id, 'spouse_only', :c1, '{}', 't1', 't1')"
                ),
                {"id": rule_spouse_only, "c1": json.dumps(cond_spouse)},
            )
            conn.execute(
                text(
                    "INSERT INTO policy_rules (id, rule_code, conditions, metadata, created_at, updated_at) "
                    "VALUES (:id, 'employee_only', :c2, '{}', 't1', 't1')"
                ),
                {"id": rule_employee, "c2": json.dumps(cond_emp)},
            )

        with self.engine.connect() as conn:
            ctx = self.svc.fetch(conn, case_id)

        roles = {p["role"] for p in ctx["people"]}
        self.assertEqual(roles, {"employee"})
        codes = {r["rule_code"] for r in ctx["applicable_rules"]}
        self.assertIn("employee_only", codes)
        self.assertNotIn("spouse_only", codes)
        self.assertEqual({r["requirement_code"] for r in ctx["requirements"]}, {"emp_req"})

    def test_non_existing_case(self) -> None:
        missing = "dddddddd-dddd-4ddd-8ddd-dddddddd0001"
        with self.engine.connect() as conn:
            ctx = self.svc.fetch(conn, missing)
        self.assertTrue(ctx["meta"]["ok"])
        self.assertFalse(ctx["meta"]["case_found"])
        self.assertIsNone(ctx["case"])
        self.assertEqual(ctx["people"], [])
        self.assertEqual(ctx["documents"], [])
        self.assertEqual(ctx["applicable_rules"], [])
        self.assertEqual(ctx["requirements"], [])
        self.assertEqual(ctx["evaluations"], [])

    def test_invalid_case_id(self) -> None:
        with self.engine.connect() as conn:
            ctx = self.svc.fetch(conn, "not-a-uuid")
        self.assertFalse(ctx["meta"]["ok"])
        self.assertEqual(ctx["meta"]["error"]["code"], "invalid_case_id")


if __name__ == "__main__":
    unittest.main()
