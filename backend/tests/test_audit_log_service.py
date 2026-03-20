"""Tests for audit_logs inserts (SQLite) and mobility case update logging."""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.audit_log_service import (  # noqa: E402
    ACTION_UPDATE,
    ACTOR_HUMAN,
    ACTOR_SYSTEM,
    insert_audit_log,
)


AUDIT_SCHEMA = """
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


class AuditLogServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with self.engine.begin() as conn:
            for stmt in AUDIT_SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

    def test_insert_log_on_case_update(self) -> None:
        case_id = str(uuid.uuid4())
        actor = str(uuid.uuid4())
        old_v = {"origin_country": "FR", "destination_country": "NO"}
        new_v = {"origin_country": "FR", "destination_country": "SE"}
        with self.engine.begin() as conn:
            log_id = insert_audit_log(
                conn,
                entity_type="mobility_cases",
                entity_id=case_id,
                action_type=ACTION_UPDATE,
                old_value=old_v,
                new_value=new_v,
                actor_type=ACTOR_HUMAN,
                actor_id=actor,
            )
            self.assertTrue(log_id)

        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT entity_type, action_type, actor_type, actor_id FROM audit_logs WHERE id = :id"),
                {"id": log_id},
            ).mappings().first()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["entity_type"], "mobility_cases")
        self.assertEqual(row["action_type"], ACTION_UPDATE)
        self.assertEqual(row["actor_type"], ACTOR_HUMAN)
        self.assertEqual(row["actor_id"], actor)

        with self.engine.connect() as conn:
            raw = conn.execute(
                text("SELECT old_value_json, new_value_json FROM audit_logs WHERE id = :id"),
                {"id": log_id},
            ).mappings().first()
        assert raw is not None
        self.assertEqual(json.loads(raw["old_value_json"]), old_v)
        self.assertEqual(json.loads(raw["new_value_json"]), new_v)

    def test_insert_system_actor_null_actor_id(self) -> None:
        eid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="case_requirement_evaluations",
                entity_id=eid,
                action_type="insert",
                old_value=None,
                new_value={"evaluation_status": "missing"},
                actor_type=ACTOR_SYSTEM,
                actor_id=None,
            )
        with self.engine.connect() as conn:
            n = conn.execute(text("SELECT count(*) AS c FROM audit_logs")).mappings().first()
        self.assertEqual(n["c"], 1)


if __name__ == "__main__":
    unittest.main()
