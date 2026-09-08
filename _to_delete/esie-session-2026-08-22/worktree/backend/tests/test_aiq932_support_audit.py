"""
AIQ-932 (slice 4) — canonical audit_logs for support-ticket writes.

In-app ticket create (human actor) and triage status update (system actor,
called by the SUPPORT-4B Edge Function) write support_tickets via the Supabase
client. events_tracker.track() is analytics, not a durable audit, so a canonical
audit_logs row is written in a dedicated SessionLocal txn. Fail-soft.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **k: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from backend.app.routers import support  # noqa: E402
from backend.app.services.audit_log_service import (  # noqa: E402
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    ACTOR_SYSTEM,
)


def _patch():
    session = MagicMock()
    sl = MagicMock()
    sl.return_value.__enter__.return_value = session
    audit = MagicMock()
    return patch.multiple(support, SessionLocal=sl, insert_audit_log=audit), audit, session


class TestSupportTicketAudit(unittest.TestCase):
    def test_create_human_actor(self):
        ctx, audit, session = _patch()
        with ctx:
            support._audit_ticket("emp-2", ACTOR_HUMAN, "tk-1", ACTION_INSERT,
                                  "support_ticket_created", {"source": "in-app"})
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "support_ticket")
        self.assertEqual(kw["entity_id"], "tk-1")
        self.assertEqual(kw["action_type"], ACTION_INSERT)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["actor_id"], "emp-2")
        self.assertEqual(kw["new_value"]["event"], "support_ticket_created")
        self.assertEqual(kw["new_value"]["source"], "in-app")
        session.commit.assert_called_once()

    def test_status_update_system_actor(self):
        ctx, audit, _ = _patch()
        with ctx:
            support._audit_ticket(None, ACTOR_SYSTEM, "tk-1", ACTION_UPDATE,
                                  "support_ticket_status_changed", {"status": "resolved"})
        kw = audit.call_args.kwargs
        self.assertEqual(kw["actor_type"], ACTOR_SYSTEM)
        self.assertEqual(kw["action_type"], ACTION_UPDATE)
        self.assertEqual(kw["new_value"]["status"], "resolved")

    def test_audit_is_failsoft(self):
        ctx, audit, _ = _patch()
        audit.side_effect = RuntimeError("db down")
        with ctx:
            support._audit_ticket("emp-2", ACTOR_HUMAN, "tk-1", ACTION_INSERT, "support_ticket_created")


if __name__ == "__main__":
    unittest.main()
