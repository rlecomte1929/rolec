"""
Tests for the audit-log wiring added to backend/app/routers/admin.py.

These don't spin up the FastAPI app (the broader test setup uses
`from main import app`, which has its own import wiring). Instead they
exercise the small `_audit_postgres` helper directly with `db.engine`
swapped to an in-memory SQLite engine, plus the audit_logs schema the
helper writes into.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import admin as admin_router  # noqa: E402
from backend.app.services.audit_log_service import ACTION_UPDATE  # noqa: E402


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


class AuditPostgresHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with self.engine.begin() as conn:
            for stmt in AUDIT_SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

    def _rows(self):
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text(
                        "SELECT entity_type, entity_id, action_type, actor_type, actor_id, "
                        "new_value_json FROM audit_logs ORDER BY created_at, id"
                    )
                ).mappings()
            )

    def test_audit_postgres_writes_row(self) -> None:
        actor = str(uuid.uuid4())
        fid = str(uuid.uuid4())
        with mock.patch.object(admin_router.db, "engine", self.engine):
            admin_router._audit_postgres(
                entity_type="requirement_facts",
                entity_id=fid,
                action_type=ACTION_UPDATE,
                new_value={"status": "approved"},
                actor_id=actor,
            )

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["entity_type"], "requirement_facts")
        self.assertEqual(row["entity_id"], fid)
        self.assertEqual(row["action_type"], ACTION_UPDATE)
        self.assertEqual(row["actor_type"], "human")
        self.assertEqual(row["actor_id"], actor)
        self.assertIn("approved", row["new_value_json"])

    def test_audit_postgres_swallows_engine_failure(self) -> None:
        broken = mock.MagicMock()
        broken.begin.side_effect = RuntimeError("engine unavailable")
        with mock.patch.object(admin_router.db, "engine", broken):
            # Must not raise — endpoint behaviour relies on this guarantee.
            admin_router._audit_postgres(
                entity_type="requirement_facts",
                entity_id=str(uuid.uuid4()),
                action_type=ACTION_UPDATE,
                new_value={"status": "approved"},
                actor_id=None,
            )
        self.assertEqual(self._rows(), [])

    def test_audit_postgres_accepts_null_actor(self) -> None:
        fid = str(uuid.uuid4())
        with mock.patch.object(admin_router.db, "engine", self.engine):
            admin_router._audit_postgres(
                entity_type="policy_documents",
                entity_id=fid,
                action_type=ACTION_UPDATE,
                old_value={"processing_status": "running"},
                new_value={"processing_status": "failed"},
                actor_id=None,
            )
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["actor_id"])
        self.assertEqual(rows[0]["actor_type"], "human")


if __name__ == "__main__":
    unittest.main()
