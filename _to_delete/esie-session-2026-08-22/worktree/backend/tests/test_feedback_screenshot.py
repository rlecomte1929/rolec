"""[AIQ-1480] Feedback screenshot storage — private Supabase Storage upload with base64 fallback.

Covers the storage helper (decode/upload/sign) in isolation, and the submit_feedback wiring:
Storage path stored in screenshot_url (base64 dropped) on success; base64 kept in
screenshot_data on failure.
"""
from __future__ import annotations

import base64
import unittest
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import backend.app.routers.feedback as fb
from backend.app.services import feedback_screenshot_storage as store

_PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
_DATA_URL = f"data:image/png;base64,{_PNG_B64}"


# ── storage helper units ──────────────────────────────────────────────────────
class StorageHelperTests(unittest.TestCase):
    def test_decode_strips_data_uri_and_detects_type(self):
        ct, raw = store._decode(_DATA_URL)
        self.assertEqual(ct, "image/png")
        self.assertEqual(raw, b"\x89PNG\r\n\x1a\nfake")
        ct2, _ = store._decode(f"data:image/jpeg;base64,{_PNG_B64}")
        self.assertEqual(ct2, "image/jpeg")

    def test_decode_rejects_garbage(self):
        self.assertIsNone(store._decode("!!!not base64!!!"))
        self.assertIsNone(store._decode(""))

    def test_upload_falls_back_to_none_when_supabase_unavailable(self):
        # get_supabase_admin_client is imported lazily inside upload_screenshot; make it raise.
        with mock.patch("backend.app.services.supabase_client.get_supabase_admin_client",
                        side_effect=RuntimeError("no supabase")):
            self.assertIsNone(store.upload_screenshot(_DATA_URL, key_hint="BUG-1"))

    def test_upload_returns_object_path_on_success(self):
        fake_bucket = mock.Mock()
        fake_client = SimpleNamespace(storage=SimpleNamespace(from_=lambda b: fake_bucket))
        with mock.patch("backend.app.services.supabase_client.get_supabase_admin_client",
                        return_value=fake_client):
            path = store.upload_screenshot(_DATA_URL, key_hint="BUG-1")
        self.assertIsNotNone(path)
        self.assertTrue(path.startswith("BUG-1-") and path.endswith(".png"))
        fake_bucket.upload.assert_called_once()

    def test_signed_url_from_client_or_none(self):
        fake_bucket = mock.Mock()
        fake_bucket.create_signed_url.return_value = {"signedURL": "https://x/y.png?token=abc"}
        fake_client = SimpleNamespace(storage=SimpleNamespace(from_=lambda b: fake_bucket))
        with mock.patch("backend.app.services.supabase_client.get_supabase_admin_client",
                        return_value=fake_client):
            self.assertEqual(store.signed_url("y.png"), "https://x/y.png?token=abc")
        with mock.patch("backend.app.services.supabase_client.get_supabase_admin_client",
                        side_effect=RuntimeError("down")):
            self.assertIsNone(store.signed_url("y.png"))


# ── submit_feedback wiring ─────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE feedback (
  id TEXT PRIMARY KEY, user_id TEXT, page_url TEXT NOT NULL, category TEXT, message TEXT,
  status TEXT DEFAULT 'new', created_at TEXT DEFAULT (datetime('now')),
  screenshot_data TEXT, screenshot_url TEXT, report_id TEXT,
  reporter_email TEXT, reporter_name TEXT, reporter_role TEXT, client_context TEXT
);
"""
_EMP = {"id": "11111111-1111-1111-1111-111111111111", "role": "EMPLOYEE", "email": "e@x.com"}


def _req():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"user-agent": "pytest"})


class SubmitWiringTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        with self.engine.begin() as c:
            c.execute(text(_SCHEMA))
        self._p = mock.patch.object(fb.db, "engine", self.engine)
        self._p.start()

    def tearDown(self):
        self._p.stop()

    def _row(self):
        with self.engine.begin() as c:
            return c.execute(text("SELECT screenshot_data, screenshot_url FROM feedback")).mappings().all()[0]

    def test_storage_success_stores_url_drops_base64(self):
        with mock.patch("backend.app.services.feedback_screenshot_storage.upload_screenshot",
                        return_value="BUG-abc-1234.png"):
            fb.submit_feedback(fb.FeedbackBody(category="bug", message="m", page_url="/x", screenshot_data=_DATA_URL), _req(), _EMP)
        row = self._row()
        self.assertEqual(row["screenshot_url"], "BUG-abc-1234.png")
        self.assertIsNone(row["screenshot_data"])  # base64 not persisted → capacity win

    def test_storage_failure_falls_back_to_base64(self):
        with mock.patch("backend.app.services.feedback_screenshot_storage.upload_screenshot", return_value=None):
            fb.submit_feedback(fb.FeedbackBody(category="bug", message="m", page_url="/x", screenshot_data=_DATA_URL), _req(), _EMP)
        row = self._row()
        self.assertIsNone(row["screenshot_url"])
        self.assertEqual(row["screenshot_data"], _DATA_URL)  # kept as fallback


if __name__ == "__main__":
    unittest.main()
