"""Wave 1 P1 — HR<->employee message SEND endpoints.

POST /api/hr/messages and POST /api/employee/messages let HR and the assigned
employee message each other on an assignment thread. Tenant isolation is enforced
in the handler (HR via _hr_can_access_assignment; employee via assignment
ownership) — the same model the read endpoints use. db is mocked, mirroring
test_employee_messages.py (the root conftest mocks backend.database).
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app, get_current_user  # noqa: E402


def _override(user_dict):
    async def _dep():
        return user_dict
    return _dep


HR_USER = {"id": "hr-1", "role": "HR", "is_admin": False, "email": "hr@example.test"}
EMPLOYEE_USER = {"id": "emp-1", "role": "EMPLOYEE", "is_admin": False, "email": "emp@example.test"}
ASSIGNMENT = {"id": "aid-1", "employee_user_id": "emp-1", "hr_user_id": "hr-1", "case_id": "case-1"}


class TestHrSendMessage(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides[get_current_user] = _override(HR_USER)

    def test_hr_can_send_to_assigned_employee(self):
        with patch("backend.main.db") as mock_db, \
             patch("backend.main._hr_can_access_assignment", return_value=True):
            mock_db.get_assignment_by_id.return_value = ASSIGNMENT
            mock_db.insert_message.return_value = {"id": "m-1", "body": "hi", "assignment_id": "aid-1"}
            resp = self.client.post("/api/hr/messages", json={"assignment_id": "aid-1", "body": "Hi Alice"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(mock_db.insert_message.called)
        kwargs = mock_db.insert_message.call_args.kwargs
        self.assertEqual(kwargs["assignment_id"], "aid-1")
        self.assertEqual(kwargs["body"], "Hi Alice")
        self.assertEqual(kwargs["sender_user_id"], "hr-1")
        self.assertEqual(kwargs["recipient_user_id"], "emp-1")

    def test_hr_forbidden_when_not_authorised_for_assignment(self):
        with patch("backend.main.db") as mock_db, \
             patch("backend.main._hr_can_access_assignment", return_value=False):
            mock_db.get_assignment_by_id.return_value = ASSIGNMENT
            resp = self.client.post("/api/hr/messages", json={"assignment_id": "aid-1", "body": "Hi"})
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertFalse(mock_db.insert_message.called)

    def test_hr_404_when_assignment_missing(self):
        with patch("backend.main.db") as mock_db:
            mock_db.get_assignment_by_id.return_value = None
            mock_db.get_assignment_by_case_id.return_value = None
            resp = self.client.post("/api/hr/messages", json={"assignment_id": "nope", "body": "Hi"})
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_hr_empty_body_rejected(self):
        with patch("backend.main.db") as mock_db, \
             patch("backend.main._hr_can_access_assignment", return_value=True):
            mock_db.get_assignment_by_id.return_value = ASSIGNMENT
            resp = self.client.post("/api/hr/messages", json={"assignment_id": "aid-1", "body": "   "})
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertFalse(mock_db.insert_message.called)


class TestEmployeeSendMessage(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides[get_current_user] = _override(EMPLOYEE_USER)

    def test_employee_can_send_on_own_assignment(self):
        with patch("backend.main.db") as mock_db:
            mock_db.get_assignment_by_id.return_value = ASSIGNMENT
            mock_db.insert_message.return_value = {"id": "m-2", "body": "hello", "assignment_id": "aid-1"}
            resp = self.client.post("/api/employee/messages", json={"assignment_id": "aid-1", "body": "Hello HR"})
        self.assertEqual(resp.status_code, 200, resp.text)
        kwargs = mock_db.insert_message.call_args.kwargs
        self.assertEqual(kwargs["sender_user_id"], "emp-1")
        self.assertEqual(kwargs["recipient_user_id"], "hr-1")

    def test_employee_forbidden_on_other_assignment(self):
        other = {"id": "aid-2", "employee_user_id": "someone-else", "hr_user_id": "hr-1"}
        with patch("backend.main.db") as mock_db:
            mock_db.get_assignment_by_id.return_value = other
            resp = self.client.post("/api/employee/messages", json={"assignment_id": "aid-2", "body": "hi"})
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertFalse(mock_db.insert_message.called)

    def test_send_routes_registered_not_405(self):
        with patch("backend.main.db") as mock_db, \
             patch("backend.main._hr_can_access_assignment", return_value=True):
            mock_db.get_assignment_by_id.return_value = ASSIGNMENT
            mock_db.insert_message.return_value = {"id": "m", "body": "x"}
            r = self.client.post("/api/employee/messages", json={"assignment_id": "aid-1", "body": "x"})
        self.assertNotEqual(r.status_code, 405)


if __name__ == "__main__":
    unittest.main()
