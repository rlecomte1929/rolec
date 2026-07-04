"""Product feedback endpoint — POST /api/feedback (Share-feedback widget).

Replaces the widget's direct Supabase insert (which failed for ReloPass-session
employees with no Supabase session). Backend writes via the service-role DB and
sets user_id explicitly. SQLite-shaped feedback table; calls the handler directly.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import backend.app.routers.feedback as fb

# Mirrors public.feedback (defaults for id/status/created_at like prod).
SCHEMA = """
CREATE TABLE feedback (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  user_id TEXT,
  page_url TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'other',
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  screenshot_data TEXT,
  report_id TEXT
);
"""

# Supabase-native session: id IS the auth.users uuid (so it's FK-valid and gets
# bound to feedback.user_id). Legacy-id → NULL is covered in test_feedback_ticket.py.
EMP = {"id": "11111111-1111-1111-1111-111111111111", "role": "EMPLOYEE", "email": "e@x.com",
       "auth_uuid": "11111111-1111-1111-1111-111111111111"}


def _req():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"),
                           headers={"user-agent": "pytest"})


class FeedbackEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        with self.engine.begin() as c:
            c.execute(text(SCHEMA))
        self._p = mock.patch.object(fb.db, "engine", self.engine)
        self._p.start()

    def tearDown(self) -> None:
        self._p.stop()

    def _rows(self):
        with self.engine.begin() as c:
            return c.execute(text(
                "SELECT user_id, page_url, category, message, status, report_id FROM feedback"
            )).mappings().all()

    def test_submit_persists_row_with_user_id(self):
        res = fb.submit_feedback(
            fb.FeedbackBody(category="bug", message="ÇVX", page_url="/messages"), _req(), EMP)
        self.assertTrue(res["ok"])
        self.assertTrue(res["report_id"].startswith("BUG-"))
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user_id"], EMP["auth_uuid"])
        self.assertEqual(rows[0]["category"], "bug")
        self.assertEqual(rows[0]["status"], "new")
        self.assertEqual(rows[0]["message"], "ÇVX")

    def test_unknown_category_falls_back_to_other(self):
        fb.submit_feedback(fb.FeedbackBody(category="weird", message="hi", page_url="/"), _req(), EMP)
        self.assertEqual(self._rows()[0]["category"], "other")

    def test_blank_message_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            fb.submit_feedback(fb.FeedbackBody(category="bug", message="   ", page_url="/"), _req(), EMP)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(len(self._rows()), 0)

    def test_oversized_screenshot_dropped_but_text_kept(self):
        big = "x" * (fb._MAX_SCREENSHOT + 1)
        fb.submit_feedback(
            fb.FeedbackBody(category="idea", message="keep me", page_url="/", screenshot_data=big),
            _req(), EMP)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["message"], "keep me")


if __name__ == "__main__":
    unittest.main()
