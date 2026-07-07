"""AIQ-1455 — every assignment gets an HR-inbox thread-starter message.

The HR inbox (/hr/messages) reads the `messages` table grouped by assignment_id.
`ensure_welcome_message_for_assignment` (run by run_assignment_post_creation_hooks on
every creation path) writes one thread-starter, idempotently.
"""
from __future__ import annotations

import unittest
from unittest import mock
from unittest.mock import MagicMock

import backend.app.services.unified_assignment_creation as uac
from backend.app.services.unified_assignment_creation import (
    ensure_welcome_message_for_assignment,
    run_assignment_post_creation_hooks,
)


def _db(existing_messages, assignment):
    db = MagicMock()
    db.list_messages_by_assignment.return_value = existing_messages
    db.get_assignment_by_id.return_value = assignment
    return db


class EnsureWelcomeMessageTests(unittest.TestCase):
    def test_writes_thread_starter_when_none_exists(self):
        db = _db([], {"id": "asg-1", "hr_user_id": "hr-1", "employee_identifier": "emp@x.com"})
        ensure_welcome_message_for_assignment(db, "asg-1")
        db.create_message.assert_called_once()
        kwargs = db.create_message.call_args.kwargs
        self.assertEqual(kwargs["assignment_id"], "asg-1")
        self.assertEqual(kwargs["hr_user_id"], "hr-1")
        self.assertEqual(kwargs["status"], "draft")

    def test_idempotent_when_a_message_already_exists(self):
        db = _db([{"id": "m1"}], {"id": "asg-1", "hr_user_id": "hr-1"})
        ensure_welcome_message_for_assignment(db, "asg-1")
        db.create_message.assert_not_called()

    def test_noop_when_assignment_missing(self):
        db = _db([], None)
        ensure_welcome_message_for_assignment(db, "asg-x")
        db.create_message.assert_not_called()

    def test_noop_when_no_hr_user(self):
        db = _db([], {"id": "asg-1", "hr_user_id": None})
        ensure_welcome_message_for_assignment(db, "asg-1")
        db.create_message.assert_not_called()

    def test_wired_into_post_creation_hooks(self):
        """The canonical hook every creation path runs must invoke the welcome-message
        hook (so admin/integration-created assignments also get an inbox thread)."""
        db = _db([], {"id": "asg-1", "hr_user_id": "hr-1", "employee_identifier": "e@x.com"})
        # Neutralise the sibling hooks so only the welcome-message behaviour is exercised.
        with mock.patch.object(uac, "_link_contact_post_create"), \
                mock.patch.object(uac, "ensure_mobility_case_link_for_assignment"), \
                mock.patch.object(uac, "ensure_employee_case_person_for_assignment"), \
                mock.patch.object(uac, "ensure_passport_case_document_for_assignment"):
            run_assignment_post_creation_hooks(db, "asg-1")
        db.create_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
