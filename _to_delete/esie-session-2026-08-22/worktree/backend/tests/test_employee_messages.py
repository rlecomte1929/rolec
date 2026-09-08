"""
AIQ-461 regression test — the employee Inbox endpoints must return 200, never 500.

Both endpoints crashed in production because the platform-redesign migration
(20260520000000) recreated public.messages with a thread-based schema, dropping the
assignment-based columns (assignment_id, recipient_user_id, read_at, dismissed_at)
that the legacy handlers query. Migration 20260529120000 restores those columns; these
tests pin the handler contract so the inbox surface stays loadable:

  1. GET /api/employee/messages   → 200 + {"messages": [], "quote_threads": []} for a
                                     fresh employee with no threads
  2. GET /api/messages/unread-count → 200 + {"count": N} for an employee with N unread
  3. Neither endpoint returns 405 (routes are registered)

No live DB needed — the db layer is patched at the module level, mirroring
test_b12_list_cases.py.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

# Disable the SQLAlchemy query-counter before importing backend.main. The root
# conftest mocks backend.database, so db.engine is a MagicMock and
# install_query_counter()'s event-listener registration raises unless the counter
# is disabled (it short-circuits on this flag). Mirrors conftest's own setdefault
# pattern for RELOPASS_DISABLE_RATE_LIMITS.
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app, get_current_user  # noqa: E402


def _override(user_dict):
    """Return an async dependency override that yields user_dict."""
    async def _dep():
        return user_dict
    return _dep


EMPLOYEE_USER = {
    "id": "emp-user-1",
    "role": "EMPLOYEE",
    "is_admin": False,
    "email": "employee@example.test",
}


class TestEmployeeMessages(unittest.TestCase):
    """AIQ-461: employee Inbox endpoints must return 200 with well-formed bodies."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Scenario 1: fresh employee, no threads → 200 + empty list
    # ------------------------------------------------------------------
    def test_fresh_employee_gets_200_empty_messages(self):
        app.dependency_overrides[get_current_user] = _override(EMPLOYEE_USER)
        with patch("backend.main.db") as mock_db:
            mock_db.list_messages_for_employee.return_value = []
            mock_db.list_quote_threads_for_employee.return_value = []
            resp = self.client.get("/api/employee/messages")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["messages"], [])
        self.assertEqual(body["quote_threads"], [])

    # ------------------------------------------------------------------
    # Scenario 2: employee with N unread → 200 + {"count": N}
    # ------------------------------------------------------------------
    def test_employee_unread_count_returns_n(self):
        app.dependency_overrides[get_current_user] = _override(EMPLOYEE_USER)
        with patch("backend.main.db") as mock_db:
            mock_db.get_unread_message_count.return_value = 3
            resp = self.client.get("/api/messages/unread-count")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["count"], 3)

    # ------------------------------------------------------------------
    # Scenario 3: zero unread → 200 + {"count": 0} (not an error state)
    # ------------------------------------------------------------------
    def test_employee_unread_count_zero(self):
        app.dependency_overrides[get_current_user] = _override(EMPLOYEE_USER)
        with patch("backend.main.db") as mock_db:
            mock_db.get_unread_message_count.return_value = 0
            resp = self.client.get("/api/messages/unread-count")

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["count"], 0)

    # ------------------------------------------------------------------
    # Scenario 4: routes are registered (not 405 Method Not Allowed)
    # ------------------------------------------------------------------
    def test_endpoints_not_405(self):
        app.dependency_overrides[get_current_user] = _override(EMPLOYEE_USER)
        with patch("backend.main.db") as mock_db:
            mock_db.list_messages_for_employee.return_value = []
            mock_db.list_quote_threads_for_employee.return_value = []
            mock_db.get_unread_message_count.return_value = 0
            r1 = self.client.get("/api/employee/messages")
            r2 = self.client.get("/api/messages/unread-count")

        self.assertNotEqual(r1.status_code, 405)
        self.assertNotEqual(r2.status_code, 405)


if __name__ == "__main__":
    unittest.main()
