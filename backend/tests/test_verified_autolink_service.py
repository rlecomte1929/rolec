"""Hermetic test for verified-email auto-link of pending_claim assignments.

Root cause of the yves-employee "not connected" bug: HR assigns before the employee
registers → assignment is written `pending_claim` and, by design, auto-reconcile skips
pending_claim rows so the employee is stuck at "Accept relocation". The fix: when the
authenticated account's email is VERIFIED and matches, the reconcile auto-links the
pending_claim assignment (no manual accept) and notifies the employee.

Uses a lightweight fake DB so it runs under the mocking conftest with no live DB.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.assignment_claim_link_service import reconcile_pending_assignment_claims


class FakeDB:
    def __init__(self, pending):
        self.pending = pending
        self.attached = []           # (assignment_id, user_id)
        self.notifications = []      # dicts
        self.linked_contacts = []
        self.pending_query_calls = 0

    # contacts
    def list_employee_contacts_matching_signup_email(self, ident, request_id=None):
        return [{"id": "contact-1", "linked_auth_user_id": None}]

    def list_employee_contacts_by_invite_key(self, ident, request_id=None):
        return []

    def link_employee_contact_to_auth_user(self, cid, uid, request_id=None):
        self.linked_contacts.append((cid, uid))

    # assignment candidate lists
    def list_unassigned_assignments_for_employee_contact(self, cid, request_id=None):
        return []  # no legacy-eligible rows

    def list_pending_claim_assignments_for_employee_contact(self, cid, request_id=None):
        self.pending_query_calls += 1
        return [dict(self.pending)]

    def list_unassigned_assignments_legacy_for_identifiers(self, idents, request_id=None):
        return []

    # attach path
    def get_assignment_by_id(self, aid, request_id=None):
        base = dict(self.pending)
        for (a, u) in self.attached:
            if a == aid:
                base["employee_user_id"] = u
        return base

    def is_assignment_auto_claim_blocked_by_revoked_invites(self, aid):
        return False

    def attach_employee_to_assignment(self, aid, uid, request_id=None):
        self.attached.append((aid, uid))

    def mark_invites_claimed(self, ident, claimed_by_user_id=None, assignment_id=None):
        pass

    # side effects
    def ensure_case_participant(self, **kwargs):
        pass

    def insert_case_event(self, **kwargs):
        pass

    def create_notification_with_preferences(self, user_id, type_, title, body=None,
                                             assignment_id=None, case_id=None, metadata=None):
        self.notifications.append({"user_id": user_id, "type": type_, "title": title,
                                   "assignment_id": assignment_id, "case_id": case_id})
        return "notif-1"


def _pending():
    return {"id": "asn-1", "case_id": "case-1", "employee_identifier": "e@x.com",
            "employee_user_id": None, "employee_link_mode": "pending_claim"}


class VerifiedAutolinkTests(unittest.TestCase):
    def test_verified_attaches_pending_claim_and_notifies(self):
        db = FakeDB(_pending())
        res = reconcile_pending_assignment_claims(
            db, user_id="u1", email="e@x.com", username=None, role="EMPLOYEE",
            attach_pending_claim=True, emit_side_effects=True,
        )
        self.assertIn("asn-1", res.newly_attached_assignment_ids)
        self.assertIn(("asn-1", "u1"), db.attached)
        self.assertTrue(
            any(n["type"] == "ASSIGNMENT_LINKED" and n["user_id"] == "u1" for n in db.notifications),
            f"expected a case-active notification, got {db.notifications}",
        )

    def test_unverified_does_not_attach_pending_claim(self):
        db = FakeDB(_pending())
        res = reconcile_pending_assignment_claims(
            db, user_id="u1", email="e@x.com", username=None, role="EMPLOYEE",
            emit_side_effects=True,  # attach_pending_claim defaults False
        )
        self.assertEqual(res.newly_attached_assignment_ids, [])
        self.assertEqual(db.attached, [])
        self.assertEqual(db.pending_query_calls, 0, "must not even query pending_claim when unverified")
        self.assertEqual(db.notifications, [])


if __name__ == "__main__":
    unittest.main()
