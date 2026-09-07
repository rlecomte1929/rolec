"""Product feedback endpoint — POST /api/feedback (Share-feedback widget).

Replaces the widget's direct Supabase insert (which failed for ReloPass-session
employees with no Supabase session). Backend writes via the service-role DB and
sets user_id explicitly. SQLite-shaped feedback table; calls the handler directly.
"""
from __future__ import annotations

import json
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
  screenshot_data TEXT, screenshot_url TEXT,
  report_id TEXT,
  reporter_email TEXT,
  reporter_name TEXT,
  reporter_role TEXT,
  client_context TEXT
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

    def test_submit_stores_reporter_identity(self):
        user = {"id": "22222222-2222-2222-2222-222222222222", "role": "HR",
                "email": "hr@x.com", "name": "Hank HR",
                "auth_uuid": "22222222-2222-2222-2222-222222222222"}
        fb.submit_feedback(fb.FeedbackBody(category="idea", message="nice"), _req(), user)
        with self.engine.begin() as c:
            r = c.execute(text(
                "SELECT reporter_email, reporter_name, reporter_role FROM feedback"
            )).mappings().all()[0]
        self.assertEqual(r["reporter_email"], "hr@x.com")
        self.assertEqual(r["reporter_name"], "Hank HR")
        self.assertEqual(r["reporter_role"], "HR")

    def test_submit_persists_client_context(self):
        ctx = {
            "route": "/hr/service-providers",
            "appVersion": "abc1234",
            "recentFailedRequests": [
                {"method": "POST", "path": "/api/hr/company-profile/logo", "status": 502,
                 "requestId": "req-1", "ts": "t"},
            ],
        }
        fb.submit_feedback(
            fb.FeedbackBody(category="bug", message="broke", page_url="/x", client_context=ctx),
            _req(), EMP)
        with self.engine.begin() as c:
            raw = c.execute(text("SELECT client_context FROM feedback")).scalar()
        self.assertIsNotNone(raw)
        parsed = json.loads(raw)
        self.assertEqual(parsed["route"], "/hr/service-providers")
        self.assertEqual(parsed["recentFailedRequests"][0]["status"], 502)

    def test_submit_without_client_context_leaves_it_null(self):
        fb.submit_feedback(fb.FeedbackBody(category="bug", message="hi", page_url="/x"), _req(), EMP)
        with self.engine.begin() as c:
            raw = c.execute(text("SELECT client_context FROM feedback")).scalar()
        self.assertIsNone(raw)

    def test_oversized_client_context_dropped_but_row_written(self):
        huge = {"blob": "x" * (fb._MAX_CLIENT_CONTEXT + 100)}
        res = fb.submit_feedback(
            fb.FeedbackBody(category="bug", message="keep", page_url="/x", client_context=huge),
            _req(), EMP)
        self.assertTrue(res["ok"])
        with self.engine.begin() as c:
            row = c.execute(text("SELECT message, client_context FROM feedback")).mappings().all()[0]
        self.assertEqual(row["message"], "keep")
        self.assertIsNone(row["client_context"])

    def test_oversized_screenshot_rejected_with_422(self):
        # [AIQ-1480] the FeedbackBody validator rejects a >5MB screenshot up front
        # (FastAPI surfaces the ValidationError as a 422), rather than silently dropping it.
        from pydantic import ValidationError
        big = "x" * (fb._MAX_SCREENSHOT + 1)
        with self.assertRaises(ValidationError):
            fb.FeedbackBody(category="idea", message="keep me", page_url="/", screenshot_data=big)

    def test_submit_captures_posthog_keyed_by_report_id_not_message(self):
        ph = mock.Mock()
        with mock.patch("backend.app.posthog_client.get_posthog_client", return_value=ph):
            res = fb.submit_feedback(
                fb.FeedbackBody(
                    category="bug",
                    message="secret passport details",
                    page_url="/admin/countries",
                    report_id="BUG-x",
                ),
                _req(),
                EMP,
            )
        self.assertTrue(res["ok"])
        self.assertEqual(res["report_id"], "BUG-x")
        ph.capture.assert_called_once()
        kwargs = ph.capture.call_args.kwargs
        self.assertEqual(kwargs["event"], "feedback_submitted")
        props = kwargs["properties"]
        self.assertEqual(props["report_id"], "BUG-x")
        self.assertEqual(props["category"], "bug")
        self.assertEqual(props["source"], "api")
        self.assertIn("/admin/countries", props["route"])
        self.assertNotIn("message", props)
        self.assertNotIn("secret passport", json.dumps(props))

    def test_submit_ok_when_posthog_client_raises(self):
        with mock.patch(
            "backend.app.posthog_client.get_posthog_client",
            side_effect=RuntimeError("posthog down"),
        ):
            res = fb.submit_feedback(
                fb.FeedbackBody(category="bug", message="hi", page_url="/x"),
                _req(),
                EMP,
            )
        self.assertTrue(res["ok"])
        self.assertIn("report_id", res)


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        return SimpleNamespace(first=lambda: self._row)


class _FakePgEngine:
    """Minimal engine that reports the postgres dialect and returns a canned auth.users
    lookup row, so we can exercise _resolve_auth_user_id's existence-check branch (which
    the SQLite test DB can't — it has no auth.users)."""

    def __init__(self, exists_row):
        self.dialect = SimpleNamespace(name="postgresql")
        self._row = exists_row

    def begin(self):
        return _FakeConn(self._row)


class ResolveAuthUserIdTests(unittest.TestCase):
    UUID = "33333333-3333-3333-3333-333333333333"

    def test_non_uuid_returns_none(self):
        self.assertIsNone(fb._resolve_auth_user_id("legacy-text-id"))
        self.assertIsNone(fb._resolve_auth_user_id(None))

    def test_pg_uuid_present_in_auth_users_is_bound(self):
        with mock.patch.object(fb.db, "engine", _FakePgEngine(exists_row=(1,))):
            self.assertEqual(fb._resolve_auth_user_id(self.UUID), self.UUID)

    def test_pg_uuid_absent_from_auth_users_is_nulled(self):
        # The bug: a uuid-format id that is NOT an auth user must NULL out (not FK-violate).
        with mock.patch.object(fb.db, "engine", _FakePgEngine(exists_row=None)):
            self.assertIsNone(fb._resolve_auth_user_id(self.UUID))


if __name__ == "__main__":
    unittest.main()
