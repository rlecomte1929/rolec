"""
One service-level integration test: live assignment lane → bridge → graph person →
passport evidence → case_documents sync → pilot catalog/rules → admin evaluation →
persisted evaluations + next-actions preview.

SQLite in-memory + patched backend.database._engine (same pattern as passport sync tests).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
from backend.database import Database
from backend.services.admin_assignment_evaluation_trigger import run_evaluation_for_assignment
from backend.services.assignment_mobility_link_service import ensure_mobility_case_link_for_assignment
from backend.services.employee_case_person_service import ensure_employee_case_person_for_assignment
from backend.services.passport_case_document_sync_service import (
    GRAPH_PASSPORT_DOCUMENT_KEY,
    ensure_passport_case_document_for_assignment,
)

# Tables not created by Database.init_db() but required by RequirementEvaluationService / audit.
_EVAL_GRAPH_DDL = """
CREATE TABLE IF NOT EXISTS requirements_catalog (
  id TEXT PRIMARY KEY,
  requirement_code TEXT NOT NULL UNIQUE,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS policy_rules (
  id TEXT PRIMARY KEY,
  rule_code TEXT NOT NULL UNIQUE,
  conditions TEXT NOT NULL DEFAULT '{}',
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS case_requirement_evaluations (
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
CREATE TABLE IF NOT EXISTS audit_logs (
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


def _seed_company(db: Database, company_id: str) -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": "Live Graph Co", "ca": now},
        )


def _ensure_eval_tables(db: Database) -> None:
    with db.engine.begin() as conn:
        for stmt in _EVAL_GRAPH_DDL.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def _seed_pilot_catalog_and_rule(conn) -> None:
    """FR→NO work_relocation pilot rule + three catalog codes (no mobility rows)."""
    for code in ("passport_valid", "passport_copy_uploaded", "signed_employment_contract"):
        conn.execute(
            text(
                "INSERT INTO requirements_catalog (id, requirement_code, metadata, created_at, updated_at) "
                "VALUES (:id, :c, '{}', 't1', 't1')"
            ),
            {"id": str(uuid.uuid4()), "c": code},
        )
    rule_id = str(uuid.uuid4())
    cond = {
        "match": {"origin_country": "FR", "destination_country": "NO", "case_type": "work_relocation"},
        "applies_to_roles": ["employee"],
        "requires_requirement_codes": [
            "passport_valid",
            "passport_copy_uploaded",
            "signed_employment_contract",
        ],
    }
    conn.execute(
        text(
            "INSERT INTO policy_rules (id, rule_code, conditions, metadata, created_at, updated_at) "
            "VALUES (:id, 'pilot_core', :c, '{}', 't1', 't1')"
        ),
        {"id": rule_id, "c": json.dumps(cond)},
    )


class MobilityLiveGraphIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self._prev_engine = dbmod._engine
        self._prev_sqlite = dbmod._is_sqlite
        dbmod._engine = eng
        dbmod._is_sqlite = True
        self.db = Database()
        _ensure_eval_tables(self.db)

    def tearDown(self) -> None:
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def test_live_assignment_passport_sync_evaluate_and_next_actions(self) -> None:
        db = self.db
        company_id = str(uuid.uuid4())
        _seed_company(db, company_id)
        hr = str(uuid.uuid4())
        emp = str(uuid.uuid4())
        reloc_case_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())

        db.create_case(reloc_case_id, hr, {}, company_id=company_id)
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE relocation_cases SET home_country = :h, host_country = :o, updated_at = :ua "
                    "WHERE id = :id"
                ),
                {"h": "FR", "o": "NO", "ua": datetime.utcnow().isoformat(), "id": reloc_case_id},
            )

        db.create_assignment(
            assignment_id=aid,
            case_id=reloc_case_id,
            hr_user_id=hr,
            employee_user_id=emp,
            employee_identifier="live-graph@example.com",
            status="assigned",
        )

        mid = ensure_mobility_case_link_for_assignment(db, aid)
        self.assertIsNotNone(mid)
        with db.engine.begin() as conn:
            row = conn.execute(
                text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :a"),
                {"a": aid},
            ).mappings().first()
        self.assertIsNotNone(row)
        self.assertEqual(str(row["mobility_case_id"]), mid)

        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE mobility_cases SET case_type = :ct, updated_at = :ua WHERE id = :id"
                ),
                {"ct": "work_relocation", "ua": datetime.utcnow().isoformat(), "id": mid},
            )
            _seed_pilot_catalog_and_rule(conn)

        ensure_employee_case_person_for_assignment(db, aid)
        with db.engine.connect() as conn:
            n_people = conn.execute(
                text("SELECT COUNT(*) AS c FROM case_people WHERE case_id = :c AND role = 'employee'"),
                {"c": mid},
            ).scalar()
        self.assertGreaterEqual(int(n_people or 0), 1)

        db.insert_case_evidence(
            case_id=reloc_case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="passport_scan",
            file_url="https://storage.example/integration-passport.pdf",
            metadata={"uploaded_by": "integration_test"},
            status="submitted",
        )
        did = ensure_passport_case_document_for_assignment(db, aid)
        self.assertIsNotNone(did)
        with db.engine.connect() as conn:
            doc = conn.execute(
                text(
                    "SELECT document_key, document_status FROM case_documents WHERE id = :id"
                ),
                {"id": did},
            ).mappings().first()
        assert doc is not None
        self.assertEqual(doc["document_key"], GRAPH_PASSPORT_DOCUMENT_KEY)
        self.assertEqual(doc["document_status"], "uploaded")

        out = run_evaluation_for_assignment(db, aid)
        self.assertTrue(out.get("ok"), msg=out)
        self.assertEqual(out.get("assignment_id"), aid)
        self.assertEqual(out.get("mobility_case_id"), mid)
        self.assertGreaterEqual(int(out.get("evaluated_count") or 0), 3)

        with db.engine.connect() as conn:
            ev_count = conn.execute(
                text("SELECT COUNT(*) AS c FROM case_requirement_evaluations WHERE case_id = :c"),
                {"c": mid},
            ).scalar()
        self.assertGreaterEqual(int(ev_count or 0), 3)

        by_code = {r["requirement_code"]: r for r in (out.get("results") or [])}
        self.assertEqual(by_code.get("passport_copy_uploaded", {}).get("evaluation_status"), "met")

        preview = out.get("next_actions_preview") or {}
        actions = preview.get("actions") or []
        self.assertGreater(len(actions), 0)
        codes = {a.get("related_requirement_code") for a in actions}
        self.assertTrue(codes & {"signed_employment_contract", "passport_valid", "passport_copy_uploaded"})


if __name__ == "__main__":
    unittest.main()
