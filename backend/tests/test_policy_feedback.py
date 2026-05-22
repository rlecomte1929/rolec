"""
Tests for [P5-5] Policy assistant feedback + HR review queue.

Validates the four hard criteria from the Notion brief (AIQ-252):
  1. Negative feedback creates a review queue entry within one transaction
  2. Positive feedback creates NO review queue entry
  3. Negative feedback does NOT modify policy_chunks / policy_values
  4. Same dedup key (company + question_hash + chunk_set) is aggregated,
     not duplicated; feedback_count crossing 3 → priority='high'

Plus the API contract:
  - PATCH /api/policy/review-queue/{id} (status/note/resolved_by)
  - GET ordering: high-priority first, then most-recently-seen
  - HR-only access on review-queue read; any-auth-user can POST feedback
  - 403 on cross-company patch
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional
from unittest import mock

from sqlalchemy import create_engine, text
from fastapi import HTTPException

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import unittest.mock as _umock  # noqa: E402
if "backend.app.auth_deps" not in sys.modules:
    _stub = _umock.MagicMock()
    _stub.get_current_user = _umock.MagicMock(return_value={"id": "u", "role": "hr"})
    sys.modules["backend.app.auth_deps"] = _stub


import backend.app.routers.policy_feedback as pf  # noqa: E402
from backend.app.routers.policy_feedback import (  # noqa: E402
    post_feedback,
    list_review_queue,
    patch_review_queue,
    FeedbackPayload,
    ReviewQueuePatch,
)


# ─────────────────────────────────────────────────────────────────────────────
# Schema — SQLite mirror of the live tables (chunk_ids stored as TEXT here)
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE companies (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE profiles (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    company_id  TEXT,
    role        TEXT NOT NULL DEFAULT 'employee'
);
CREATE TABLE policy_chunks (
    id    TEXT PRIMARY KEY,
    text  TEXT
);
CREATE TABLE policy_values (
    id          TEXT PRIMARY KEY,
    company_id  TEXT,
    cap_value   REAL
);
CREATE TABLE policy_feedback (
    id              TEXT PRIMARY KEY,
    company_id      TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    question_hash   TEXT NOT NULL,
    chunk_ids       TEXT NOT NULL DEFAULT '',
    rating          TEXT NOT NULL CHECK (rating IN ('positive', 'negative')),
    comment         TEXT,
    created_at      TEXT NOT NULL
);
CREATE TABLE policy_review_queue (
    id              TEXT PRIMARY KEY,
    company_id      TEXT NOT NULL,
    question_hash   TEXT NOT NULL,
    chunk_ids       TEXT NOT NULL DEFAULT '',
    chunk_ids_key   TEXT GENERATED ALWAYS AS (chunk_ids) STORED,
    response_summary TEXT,
    latest_comment  TEXT,
    feedback_count  INTEGER NOT NULL DEFAULT 1,
    priority        TEXT NOT NULL DEFAULT 'normal',
    status          TEXT NOT NULL DEFAULT 'pending',
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    resolved_by     TEXT,
    resolved_at     TEXT,
    resolution_note TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX uq_policy_review_queue_dedup
    ON policy_review_queue (company_id, question_hash, chunk_ids_key);
"""


def _uuid() -> str:
    return str(uuid.uuid4())


def _seed_company(conn, *, cid: str) -> None:
    conn.execute(text("INSERT INTO companies (id, name) VALUES (:id, 'Acme')"),
                 {"id": cid})


def _seed_profile(conn, *, pid: str, email: str, company_id: str,
                  role: str = "employee") -> None:
    conn.execute(text(
        "INSERT INTO profiles (id, email, company_id, role) "
        "VALUES (:id, :e, :c, :r)"
    ), {"id": pid, "e": email, "c": company_id, "r": role})


def _seed_policy_chunk(conn, *, cid: str, text_body: str = "chunk text") -> None:
    conn.execute(text("INSERT INTO policy_chunks (id, text) VALUES (:id, :t)"),
                 {"id": cid, "t": text_body})


def _seed_policy_value(conn, *, vid: str, company_id: str, cap: float = 1000.0) -> None:
    conn.execute(text(
        "INSERT INTO policy_values (id, company_id, cap_value) "
        "VALUES (:id, :c, :v)"
    ), {"id": vid, "c": company_id, "v": cap})


def _user(uid: str, company_id: str, role: str = "employee") -> Dict[str, Any]:
    return {"id": uid, "company_id": company_id, "role": role}


# ─────────────────────────────────────────────────────────────────────────────
# Test suite
# ─────────────────────────────────────────────────────────────────────────────

class PolicyFeedbackTests(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        self.engine_patcher = mock.patch.object(pf.db, "engine", self.engine)
        self.engine_patcher.start()

    def tearDown(self):
        self.engine_patcher.stop()
        self.engine.dispose()

    def _bootstrap(self):
        cid = _uuid()
        emp_id = _uuid()
        hr_id = _uuid()
        chunk_a, chunk_b = _uuid(), _uuid()
        pv_id = _uuid()
        with self.engine.begin() as conn:
            _seed_company(conn, cid=cid)
            _seed_profile(conn, pid=emp_id, email="e@acme.test",
                          company_id=cid, role="employee")
            _seed_profile(conn, pid=hr_id, email="hr@acme.test",
                          company_id=cid, role="hr")
            _seed_policy_chunk(conn, cid=chunk_a)
            _seed_policy_chunk(conn, cid=chunk_b)
            _seed_policy_value(conn, vid=pv_id, company_id=cid)
        return {
            "company_id": cid, "emp_id": emp_id, "hr_id": hr_id,
            "chunk_a": chunk_a, "chunk_b": chunk_b, "pv_id": pv_id,
        }

    def _count(self, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text(sql), params or {}).scalar()

    # ── Criterion 1 + 3 : thumbs-down → queue entry, no value mutation ──────

    def test_negative_creates_review_queue_entry(self):
        ctx = self._bootstrap()
        res = post_feedback(
            FeedbackPayload(
                session_id="sess-1",
                question_hash="a" * 64,
                chunk_ids=[ctx["chunk_a"], ctx["chunk_b"]],
                rating="negative",
                comment="answer was wrong",
                response_summary="Manager housing cap is EUR 3,000",
            ),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        self.assertIsNotNone(res.review_queue_id)
        self.assertEqual(res.feedback_count, 1)
        self.assertEqual(res.priority, "normal")

        self.assertEqual(self._count("SELECT count(*) FROM policy_feedback"), 1)
        self.assertEqual(self._count("SELECT count(*) FROM policy_review_queue"), 1)

    def test_negative_does_not_mutate_chunks_or_values(self):
        ctx = self._bootstrap()
        chunks_before = self._count("SELECT count(*) FROM policy_chunks")
        values_before = self._count(
            "SELECT count(*) FROM policy_values WHERE company_id = :c",
            {"c": ctx["company_id"]},
        )
        post_feedback(
            FeedbackPayload(
                session_id="sess-1", question_hash="a" * 64,
                chunk_ids=[ctx["chunk_a"]], rating="negative",
            ),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        # No change in chunks or values
        self.assertEqual(
            self._count("SELECT count(*) FROM policy_chunks"), chunks_before
        )
        self.assertEqual(
            self._count(
                "SELECT count(*) FROM policy_values WHERE company_id = :c",
                {"c": ctx["company_id"]},
            ),
            values_before,
        )

    # ── Criterion 2 : positive → no queue entry ─────────────────────────────

    def test_positive_does_not_create_queue_entry(self):
        ctx = self._bootstrap()
        res = post_feedback(
            FeedbackPayload(
                session_id="sess-1", question_hash="a" * 64,
                chunk_ids=[ctx["chunk_a"]], rating="positive",
            ),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        self.assertIsNone(res.review_queue_id)
        self.assertEqual(self._count("SELECT count(*) FROM policy_feedback"), 1)
        self.assertEqual(self._count("SELECT count(*) FROM policy_review_queue"), 0)

    # ── Criterion 4 : dedup and priority escalation ─────────────────────────

    def test_duplicate_negative_increments_count_not_rows(self):
        ctx = self._bootstrap()
        for i in range(3):
            post_feedback(
                FeedbackPayload(
                    session_id=f"sess-{i}", question_hash="a" * 64,
                    chunk_ids=[ctx["chunk_a"], ctx["chunk_b"]],
                    rating="negative",
                ),
                _user(ctx["emp_id"], ctx["company_id"]),
            )
        # 3 raw feedback rows, 1 queue row
        self.assertEqual(self._count("SELECT count(*) FROM policy_feedback"), 3)
        self.assertEqual(self._count("SELECT count(*) FROM policy_review_queue"), 1)

        row = list_review_queue(
            status="pending", priority=None,
            user=_user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )[0]
        self.assertEqual(row.feedback_count, 3)
        self.assertEqual(row.priority, "high")  # 3rd one escalates

    def test_feedback_count_2_stays_normal(self):
        ctx = self._bootstrap()
        for i in range(2):
            post_feedback(
                FeedbackPayload(
                    session_id=f"sess-{i}", question_hash="a" * 64,
                    chunk_ids=[ctx["chunk_a"]], rating="negative",
                ),
                _user(ctx["emp_id"], ctx["company_id"]),
            )
        row = list_review_queue(
            status="pending", priority=None,
            user=_user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )[0]
        self.assertEqual(row.feedback_count, 2)
        self.assertEqual(row.priority, "normal")

    def test_chunk_order_does_not_affect_dedup_key(self):
        """Citing chunks in different order must still map to the same row."""
        ctx = self._bootstrap()
        post_feedback(
            FeedbackPayload(
                session_id="s1", question_hash="a" * 64,
                chunk_ids=[ctx["chunk_a"], ctx["chunk_b"]],
                rating="negative",
            ),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        post_feedback(
            FeedbackPayload(
                session_id="s2", question_hash="a" * 64,
                chunk_ids=[ctx["chunk_b"], ctx["chunk_a"]],  # reversed
                rating="negative",
            ),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        self.assertEqual(self._count("SELECT count(*) FROM policy_review_queue"), 1)

    def test_different_question_hash_creates_separate_queue_row(self):
        ctx = self._bootstrap()
        post_feedback(
            FeedbackPayload(session_id="s1", question_hash="a" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        post_feedback(
            FeedbackPayload(session_id="s2", question_hash="b" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        self.assertEqual(self._count("SELECT count(*) FROM policy_review_queue"), 2)

    def test_latest_comment_is_overwritten_on_each_negative(self):
        ctx = self._bootstrap()
        post_feedback(
            FeedbackPayload(session_id="s1", question_hash="a" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative",
                            comment="first comment"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        post_feedback(
            FeedbackPayload(session_id="s2", question_hash="a" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative",
                            comment="second comment"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        row = list_review_queue(
            status="pending", priority=None,
            user=_user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )[0]
        self.assertEqual(row.latest_comment, "second comment")

    # ── GET /review-queue contract ──────────────────────────────────────────

    def test_list_review_queue_high_priority_first(self):
        ctx = self._bootstrap()
        # Hash B: 3 negatives → priority='high'
        for i in range(3):
            post_feedback(
                FeedbackPayload(session_id=f"sb{i}", question_hash="b" * 64,
                                chunk_ids=[ctx["chunk_b"]], rating="negative"),
                _user(ctx["emp_id"], ctx["company_id"]),
            )
        # Hash A: 1 negative → priority='normal'
        post_feedback(
            FeedbackPayload(session_id="sa", question_hash="a" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )

        rows = list_review_queue(
            status="pending", priority=None,
            user=_user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].priority, "high")
        self.assertEqual(rows[1].priority, "normal")

    def test_list_review_queue_403_for_employee(self):
        ctx = self._bootstrap()
        with self.assertRaises(HTTPException) as e:
            list_review_queue(
                status="pending", priority=None,
                user=_user(ctx["emp_id"], ctx["company_id"], role="employee"),
            )
        self.assertEqual(e.exception.status_code, 403)

    def test_post_feedback_403_when_no_company(self):
        with self.assertRaises(HTTPException) as e:
            post_feedback(
                FeedbackPayload(session_id="s", question_hash="a" * 64,
                                chunk_ids=[], rating="positive"),
                {"id": _uuid(), "role": "employee", "company_id": None},
            )
        self.assertEqual(e.exception.status_code, 403)

    # ── PATCH /review-queue/{id} ────────────────────────────────────────────

    def test_patch_status_to_resolved_sets_resolved_by_at(self):
        ctx = self._bootstrap()
        post_feedback(
            FeedbackPayload(session_id="s", question_hash="a" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        rows = list_review_queue(
            status="pending", priority=None,
            user=_user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )
        qid = rows[0].id

        res = patch_review_queue(
            qid,
            ReviewQueuePatch(status="resolved", resolution_note="Fixed in v3"),
            _user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )
        self.assertEqual(res.status, "resolved")
        self.assertEqual(res.resolved_by, ctx["hr_id"])
        self.assertEqual(res.resolution_note, "Fixed in v3")
        self.assertIsNotNone(res.resolved_at)

    def test_patch_403_cross_company(self):
        ctx = self._bootstrap()
        post_feedback(
            FeedbackPayload(session_id="s", question_hash="a" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        rows = list_review_queue(
            status="pending", priority=None,
            user=_user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )
        qid = rows[0].id

        with self.assertRaises(HTTPException) as e:
            patch_review_queue(
                qid,
                ReviewQueuePatch(status="dismissed"),
                _user(_uuid(), _uuid(), role="hr"),  # different company
            )
        self.assertEqual(e.exception.status_code, 403)

    def test_patch_404_unknown_queue_id(self):
        ctx = self._bootstrap()
        with self.assertRaises(HTTPException) as e:
            patch_review_queue(
                _uuid(),
                ReviewQueuePatch(status="dismissed"),
                _user(ctx["hr_id"], ctx["company_id"], role="hr"),
            )
        self.assertEqual(e.exception.status_code, 404)

    def test_patch_400_empty_payload(self):
        ctx = self._bootstrap()
        post_feedback(
            FeedbackPayload(session_id="s", question_hash="a" * 64,
                            chunk_ids=[ctx["chunk_a"]], rating="negative"),
            _user(ctx["emp_id"], ctx["company_id"]),
        )
        rows = list_review_queue(
            status="pending", priority=None,
            user=_user(ctx["hr_id"], ctx["company_id"], role="hr"),
        )
        qid = rows[0].id

        with self.assertRaises(HTTPException) as e:
            patch_review_queue(
                qid, ReviewQueuePatch(),
                _user(ctx["hr_id"], ctx["company_id"], role="hr"),
            )
        self.assertEqual(e.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
