"""AIQ-1092 (P4-03) — list + approve/reject for requirement_fact_candidates.

SQLite-backed (mirrors test_ai_decisions_router.py): a real in-memory table + db.engine patched,
endpoint functions called directly with a fake admin (DI bypassed). No DATABASE_URL at import.
"""
from __future__ import annotations

import unittest
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text

import backend.app.routers.requirement_facts as rf

SCHEMA = """
CREATE TABLE requirement_fact_candidates (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  source_url TEXT NOT NULL,
  corridor TEXT,
  requirement_type TEXT NOT NULL,
  fact_text TEXT NOT NULL,
  confidence_score REAL NOT NULL,
  source_quote TEXT,
  extraction_method TEXT NOT NULL DEFAULT 'llm',
  status TEXT NOT NULL DEFAULT 'pending',
  reviewed_by TEXT,
  reviewed_at TEXT
);
"""

_ADMIN = {"id": "admin-uuid-1", "is_admin": True, "email": "admin@relopass.com"}


def _seed(conn, id_, status, rtype="document", conf=0.9):
    conn.execute(
        text(
            "INSERT INTO requirement_fact_candidates "
            "(id, created_at, source_url, corridor, requirement_type, fact_text, confidence_score, "
            " source_quote, extraction_method, status) "
            "VALUES (:id, :ts, :url, :corr, :rt, :ft, :c, :q, 'llm', :st)"
        ),
        {"id": id_, "ts": "2026-06-29T00:00:00", "url": "https://gov.example", "corr": "IN-DE",
         "rt": rtype, "ft": f"fact {id_}", "c": conf, "q": "quote", "st": status},
    )


class RequirementFactsReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
            _seed(conn, "f1", "pending", conf=0.9)
            _seed(conn, "f2", "pending", conf=0.4)
            _seed(conn, "f3", "approved", conf=0.7)
        patcher = mock.patch.object(rf.db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _status_of(self, id_):
        with self.engine.connect() as conn:
            return conn.execute(
                text("SELECT status, reviewed_by FROM requirement_fact_candidates WHERE id = :id"),
                {"id": id_},
            ).mappings().first()

    def test_list_pending_returns_only_pending(self):
        rows = rf.list_requirement_facts(status="pending", limit=100, user=_ADMIN)
        ids = {r["id"] for r in rows}
        self.assertEqual(ids, {"f1", "f2"})
        # serialized shape
        self.assertIsInstance(rows[0]["confidence_score"], float)
        self.assertIn("source_quote", rows[0])

    def test_list_approved(self):
        rows = rf.list_requirement_facts(status="approved", limit=100, user=_ADMIN)
        self.assertEqual([r["id"] for r in rows], ["f3"])

    def test_patch_approve_flips_status_and_records_reviewer(self):
        out = rf.review_requirement_fact("f1", rf.RequirementFactReview(status="approved"), user=_ADMIN)
        self.assertEqual(out["status"], "approved")
        self.assertEqual(out["reviewed_by"], "admin-uuid-1")
        self.assertIsNotNone(out["reviewed_at"])
        # dropped from pending
        remaining = {r["id"] for r in rf.list_requirement_facts(status="pending", limit=100, user=_ADMIN)}
        self.assertEqual(remaining, {"f2"})

    def test_patch_reject(self):
        rf.review_requirement_fact("f2", rf.RequirementFactReview(status="rejected"), user=_ADMIN)
        self.assertEqual(self._status_of("f2")["status"], "rejected")

    def test_patch_unknown_id_404(self):
        with self.assertRaises(HTTPException) as ctx:
            rf.review_requirement_fact("nope", rf.RequirementFactReview(status="approved"), user=_ADMIN)
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
