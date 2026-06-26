"""
[AIQ-1237] Tests for the weekly mobility status cron.

Strategy: in-memory SQLite with the minimal schema the cron touches
(case_milestones, cases, profiles). Mirrors test_milestone_reminders.py.
RESEND_API_KEY is unset, so the shared Resend path returns 'no_key' and the
digest is counted as 'logged' (no network) — exactly the dev posture.

Covers:
  - overdue steps on an active case are grouped into ONE digest per HR owner
  - multiple HR owners get separate digests
  - done/skipped, future-dated, and inactive-case milestones are excluded
  - the rendered email reflects employee, step, and days-overdue
"""
from __future__ import annotations

import os
import sys
import unittest
import unittest.mock as _umock
import uuid
from datetime import datetime, timedelta, timezone

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

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
    hr_owner_id TEXT,
    status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS case_milestones (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    canonical_case_id TEXT,
    title TEXT,
    target_date TEXT,
    status TEXT DEFAULT 'pending'
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


class WeeklyMobilityStatusTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("RESEND_API_KEY", None)  # force the logged (no-send) path
        self.engine = _make_engine()
        import importlib
        import backend.app.services.weekly_mobility_status as _wm
        importlib.reload(_wm)
        self._wm = _wm
        _wm._engine = lambda: self.engine  # type: ignore[attr-defined]

        self.emp_id = str(uuid.uuid4())
        self.hr_id = str(uuid.uuid4())
        self.case_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO profiles VALUES (:id,'Alice Employee','alice@example.com')"),
                         {"id": self.emp_id})
            conn.execute(text("INSERT INTO profiles VALUES (:id,'Bob HR','bob@example.com')"),
                         {"id": self.hr_id})
            conn.execute(
                text("INSERT INTO cases (id,employee_id,hr_owner_id,status) VALUES (:id,:e,:h,'active')"),
                {"id": self.case_id, "e": self.emp_id, "h": self.hr_id},
            )

    def _seed_milestone(self, *, days_out: int, status="pending", title="Register with police", case_id=None):
        mid = str(uuid.uuid4())
        cid = case_id or self.case_id
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_milestones (id,case_id,canonical_case_id,title,target_date,status) "
                     "VALUES (:id,:cid,:cid,:title,:td,:st)"),
                {"id": mid, "cid": cid, "title": title, "td": _iso_in(days_out), "st": status},
            )
        return mid

    def test_overdue_step_emits_one_digest(self):
        self._seed_milestone(days_out=-5)
        res = self._wm.run_weekly_mobility_status_cron()
        self.assertEqual(res["overdue_steps"], 1)
        self.assertEqual(res["hr_admins"], 1)
        self.assertEqual(res["logged"], 1)  # no RESEND_API_KEY -> logged, not sent
        self.assertEqual(res["sent"], 0)
        self.assertEqual(res["failed"], 0)

    def test_multiple_overdue_grouped_into_single_digest(self):
        self._seed_milestone(days_out=-2, title="Open a bank account")
        self._seed_milestone(days_out=-10, title="Register with police")
        res = self._wm.run_weekly_mobility_status_cron()
        self.assertEqual(res["overdue_steps"], 2)
        self.assertEqual(res["hr_admins"], 1)   # one HR owner -> one email
        self.assertEqual(res["logged"], 1)

    def test_two_hr_owners_get_separate_digests(self):
        hr2 = str(uuid.uuid4())
        case2 = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO profiles VALUES (:id,'Carol HR','carol@example.com')"), {"id": hr2})
            conn.execute(
                text("INSERT INTO cases (id,employee_id,hr_owner_id,status) VALUES (:id,:e,:h,'active')"),
                {"id": case2, "e": self.emp_id, "h": hr2},
            )
        self._seed_milestone(days_out=-1)
        self._seed_milestone(days_out=-1, case_id=case2)
        res = self._wm.run_weekly_mobility_status_cron()
        self.assertEqual(res["overdue_steps"], 2)
        self.assertEqual(res["hr_admins"], 2)
        self.assertEqual(res["logged"], 2)

    def test_excludes_future_done_skipped_and_inactive(self):
        self._seed_milestone(days_out=3)                    # not yet due
        self._seed_milestone(days_out=-1, status="done")    # finished
        self._seed_milestone(days_out=-1, status="skipped") # finished
        # overdue but on an inactive case -> excluded
        closed_case = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id,employee_id,hr_owner_id,status) VALUES (:id,:e,:h,'closed')"),
                {"id": closed_case, "e": self.emp_id, "h": self.hr_id},
            )
        self._seed_milestone(days_out=-4, case_id=closed_case)
        res = self._wm.run_weekly_mobility_status_cron()
        self.assertEqual(res["overdue_steps"], 0)
        self.assertEqual(res["hr_admins"], 0)

    def test_render_reflects_step_and_days_overdue(self):
        subject, plain, html = self._wm.render_weekly_mobility_email(
            hr_name="Bob HR",
            items=[{"employee_name": "Alice", "step": "Register with police",
                    "target_date": "2026-06-01", "days_overdue": 5}],
        )
        self.assertIn("1 step overdue", subject)
        self.assertIn("Alice", plain)
        self.assertIn("Register with police", plain)
        self.assertIn("5 days overdue", plain)
        self.assertIn("Alice", html)


if __name__ == "__main__":
    unittest.main()
