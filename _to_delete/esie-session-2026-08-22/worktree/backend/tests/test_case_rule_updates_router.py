"""P2-02e · case rule-update notifications router wiring (AIQ-693).

Verifies the case-scoped endpoints are registered on the production app
(backend.main:app) and reject unauthenticated callers. The list/dismiss DB
behaviour is covered by test_case_rule_update_service (unit); the live HTTP path
needs the Postgres migration applied (the test app runs on SQLite).
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

_LIST = "/api/cases/{case_id}/rule-updates"
_DISMISS = "/api/cases/{case_id}/rule-updates/{notification_id}/dismiss"


class RouterWiringTests(unittest.TestCase):
    def test_routes_registered_on_prod_app(self) -> None:
        routes = {
            (r.path, m)
            for r in app.routes
            for m in (getattr(r, "methods", None) or set())
            if "rule-updates" in getattr(r, "path", "")
        }
        self.assertIn((_LIST, "GET"), routes)
        self.assertIn((_DISMISS, "POST"), routes)

    def test_endpoints_require_auth(self) -> None:
        client = TestClient(app)
        self.assertIn(client.get("/api/cases/case-1/rule-updates").status_code, (401, 403))
        self.assertIn(
            client.post("/api/cases/case-1/rule-updates/n1/dismiss").status_code, (401, 403)
        )

    def test_routes_exist_not_405(self) -> None:
        client = TestClient(app)
        self.assertNotEqual(client.get("/api/cases/case-1/rule-updates").status_code, 405)
        self.assertNotEqual(
            client.post("/api/cases/case-1/rule-updates/n1/dismiss").status_code, 405
        )


if __name__ == "__main__":
    unittest.main()
