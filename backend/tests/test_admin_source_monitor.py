"""
[P3-02b] Tests for the admin source-monitor endpoint
GET /api/admin/freshness/source-pages — lists all source_pages rows.
"""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.routers import admin_freshness

PATH = "/api/admin/freshness/source-pages"

_FAKE_ROWS = [
    {
        "id": "1", "url": "https://oslo.kommune.no/register", "tier": "1",
        "content_hash": "abc123", "previous_hash": None, "page_title": "Register",
        "http_status": 200, "is_accessible": True,
        "last_fetched_at": "2026-06-04T08:00:00Z", "last_changed_at": "2026-06-01T08:00:00Z",
    },
]


class TestSourceMonitorEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(admin_freshness._require_admin, None)

    def test_requires_auth(self):
        r = self.client.get(PATH)
        self.assertEqual(r.status_code, 401)

    def test_returns_source_pages_rows_for_admin(self):
        app.dependency_overrides[admin_freshness._require_admin] = lambda: {"id": "u1", "role": "ADMIN"}
        with patch.object(admin_freshness, "list_source_monitor_pages", return_value=_FAKE_ROWS) as mock_list:
            r = self.client.get(PATH)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["url"], "https://oslo.kommune.no/register")
        self.assertEqual(body["items"][0]["tier"], "1")
        mock_list.assert_called_once()


if __name__ == "__main__":
    unittest.main()
