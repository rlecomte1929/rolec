"""P2-02d · admin material-change review router wiring (AIQ-692).

Verifies the dual-mounted admin endpoints are registered on the production app
(backend.main:app) and gated to admins. The approve/reject DB behaviour is
covered by test_source_change_review_service (unit) and the migration smoke test;
the live HTTP path needs the Postgres migration applied (the test app runs on
SQLite), so it is not exercised here.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi.testclient import TestClient

from backend.main import app

_BASE = "/api/admin/source-change-reviews"


class RouterWiringTests(unittest.TestCase):
    def test_all_three_routes_registered_on_prod_app(self) -> None:
        routes = {
            (r.path, m)
            for r in app.routes
            for m in (getattr(r, "methods", None) or set())
            if "source-change-reviews" in getattr(r, "path", "")
        }
        self.assertIn((_BASE, "GET"), routes)
        self.assertIn((_BASE + "/{review_id}/approve", "POST"), routes)
        self.assertIn((_BASE + "/{review_id}/reject", "POST"), routes)

    def test_endpoints_require_auth(self) -> None:
        client = TestClient(app)
        # No credentials → must be rejected, never reachable anonymously.
        self.assertIn(client.get(_BASE).status_code, (401, 403))
        self.assertIn(client.post(_BASE + "/abc/approve").status_code, (401, 403))
        self.assertIn(client.post(_BASE + "/abc/reject").status_code, (401, 403))

    def test_routes_exist_not_405(self) -> None:
        # A 405 would mean the method/route isn't registered (the dual-mount bug).
        client = TestClient(app)
        self.assertNotEqual(client.get(_BASE).status_code, 405)
        self.assertNotEqual(client.post(_BASE + "/abc/approve").status_code, 405)


if __name__ == "__main__":
    unittest.main()
