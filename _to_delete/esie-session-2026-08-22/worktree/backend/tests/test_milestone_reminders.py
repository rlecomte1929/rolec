"""
[AIQ-656] Tests for the milestone reminder cron (D-7 / D-3 / D-0).

Strategy: in-memory SQLite with the minimal schema the cron touches
(case_milestones, cases, profiles, notification_outbox, case_milestone_reminders).
Mirrors test_dossier_notifications.py.

Covers the 4 validation criteria:
  1-2) target_date = today + 7/3/0 -> exactly one notification_outbox row each.
  3)   re-running the cron does NOT double-fire (idempotency = milestone_id+offset).
  4)   one full milestone lifecycle (created -> reminded -> done -> no more).
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

# ── Repo root on sys.path ────────────────────────────────────────────────────
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# ── Stub heavy backend.database before importing the service ─────────────────
import unittest.mock as _umock
if "backend.database" not in sys.modules:
    sys.modules["backend.database"] = _umock.MagicMock()

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_DDL = """
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    full_name TEXT,
    email TEXT
);
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    employee_id TEXT,
    hr_owner_id TEXT
);
CREATE TABLE IF NOT EXISTS case_milestones (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    canonical_case_id TEXT,
    milestone_type TEXT,
    title TEXT,
    target_date TEXT,
    status TEXT DEFAULT 'pending',
    owner TEXT DEFAULT 'joint'
);
CREATE TABLE IF NOT EXISTS notification_outbox (
    id TEXT PRIMARY KEY,
    notification_id TEXT,
    user_id TEXT NOT NULL,
    to_email TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS case_milestone_reminders (
    milestone_id TEXT NOT NULL,
    day_offset INTEGER NOT NULL,
    recipient_user_id TEXT,
    to_email TEXT,
    sent_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (milestone_id, day_offset)
);
"""


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _DDL.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt.strip()))
    return engine


def _iso_in(n: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=n)).isoformat()


class MilestoneReminderTest(unittest.TestCase):
    def setUp(self):
        self.engine = _make_engine()
        import importlib
        import backend.app.services.milestone_reminders as _mr
        importlib.reload(_mr)
        self._mr = _mr
        _mr._engine = lambda: self.engine  # type: ignore[attr-defined]

        self.emp_id = str(uuid.uuid4())
        self.hr_id = str(uuid.uuid4())
        self.case_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO profiles VALUES (:id,'Alice Employee','alice@example.com')"),
                         {"id": self.emp_id})
            conn.execute(text("INSERT INTO profiles VALUES (:id,'Bob HR','bob@example.com')"),
                         {"id": self.hr_id})
            conn.execute(text("INSERT INTO cases (id,employee_id,hr_owner_id) VALUES (:id,:e,:h)"),
                         {"id": self.case_id, "e": self.emp_id, "h": self.hr_id})

    def _seed_milestone(self, *, days_out: int, status="pending", owner="joint", title="Register with police"):
        mid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO case_milestones (id,case_id,canonical_case_id,milestone_type,title,target_date,status,owner) "
                "VALUES (:id,:cid,:cid,'immigration',:title,:td,:st,:owner)"
            ), {"id": mid, "cid": self.case_id, "title": title,
                "td": _iso_in(days_out), "st": status, "owner": owner})
        return mid

    def _outbox(self):
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT * FROM notification_outbox")).mappings().all()

    # ── Criteria 1 & 2: a milestone at +7 / +3 / +0 fires exactly one row ──
    def test_fires_at_each_offset(self):
        for off in (7, 3, 0):
            with self.subTest(offset=off):
                self.setUp()  # fresh DB per offset
                mid = self._seed_milestone(days_out=off)
                res = self._mr.run_milestone_reminder_cron()
                self.assertEqual(res["reminded"], 1)
                rows = self._outbox()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["type"], "milestone.reminder")
                self.assertEqual(rows[0]["to_email"], "alice@example.com")
                self.assertIn(f"{mid}:{off}", rows[0]["payload"])
                self.assertEqual(rows[0]["status"], "pending")

    # ── Criterion 3: idempotency — re-run does not double-fire ──
    def test_idempotent_on_rerun(self):
        self._seed_milestone(days_out=7)
        self._mr.run_milestone_reminder_cron()
        second = self._mr.run_milestone_reminder_cron()
        self.assertEqual(second["reminded"], 0)
        self.assertEqual(len(self._outbox()), 1)

    # ── A milestone NOT at an offset boundary is ignored ──
    def test_ignores_non_due_milestone(self):
        self._seed_milestone(days_out=5)
        res = self._mr.run_milestone_reminder_cron()
        self.assertEqual(res["reminded"], 0)
        self.assertEqual(len(self._outbox()), 0)

    # ── done/skipped milestones never fire ──
    def test_skips_finished_milestones(self):
        self._seed_milestone(days_out=0, status="done")
        self._seed_milestone(days_out=0, status="skipped")
        res = self._mr.run_milestone_reminder_cron()
        self.assertEqual(res["reminded"], 0)
        self.assertEqual(len(self._outbox()), 0)

    # ── owner='hr' routes to the HR email ──
    def test_hr_owner_routes_to_hr(self):
        self._seed_milestone(days_out=3, owner="hr")
        self._mr.run_milestone_reminder_cron()
        rows = self._outbox()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["to_email"], "bob@example.com")

    # ── no resolvable email -> skipped, no crash ──
    def test_no_recipient_is_skipped(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE profiles SET email=NULL"))
        self._seed_milestone(days_out=7)
        res = self._mr.run_milestone_reminder_cron()
        self.assertEqual(res["reminded"], 0)
        self.assertEqual(res["skipped_no_recipient"], 1)

    # ── Criterion 4: one full milestone lifecycle ──
    def test_full_lifecycle(self):
        mid = self._seed_milestone(days_out=7)
        # D-7 fires
        self.assertEqual(self._mr.run_milestone_reminder_cron()["reminded"], 1)
        # Move target so it is now 3 days out -> D-3 fires (distinct offset)
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE case_milestones SET target_date=:td WHERE id=:id"),
                         {"td": _iso_in(3), "id": mid})
        self.assertEqual(self._mr.run_milestone_reminder_cron()["reminded"], 1)
        # Now 0 days out -> D-0 fires
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE case_milestones SET target_date=:td WHERE id=:id"),
                         {"td": _iso_in(0), "id": mid})
        self.assertEqual(self._mr.run_milestone_reminder_cron()["reminded"], 1)
        # Three distinct reminders, one per offset
        self.assertEqual(len(self._outbox()), 3)
        with self.engine.connect() as conn:
            offsets = {r["day_offset"] for r in
                       conn.execute(text("SELECT day_offset FROM case_milestone_reminders")).mappings().all()}
        self.assertEqual(offsets, {7, 3, 0})
        # Mark done -> no further reminders even if re-run
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE case_milestones SET status='done' WHERE id=:id"), {"id": mid})
        self.assertEqual(self._mr.run_milestone_reminder_cron()["reminded"], 0)


if __name__ == "__main__":
    unittest.main()
