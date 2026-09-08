"""
AIQ-932 (slice 5) — canonical audit_logs for relocation-policy writes.

create/update/activate write relocation_policies via the Supabase client (no
SQLAlchemy router conn), so a durable audit_logs row is written in a dedicated
SessionLocal txn. Exercises the fail-soft helper directly.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **k: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from backend.app.routers import hr_policies  # noqa: E402
from backend.app.services.audit_log_service import (  # noqa: E402
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
)

USER = {"id": "hr-5", "role": "hr"}


def _patch():
    session = MagicMock()
    sl = MagicMock()
    sl.return_value.__enter__.return_value = session
    audit = MagicMock()
    return patch.multiple(hr_policies, SessionLocal=sl, insert_audit_log=audit), audit, session


class TestPolicyAudit(unittest.TestCase):
    def test_create_audited(self):
        ctx, audit, session = _patch()
        with ctx:
            hr_policies._audit_policy(USER, "pol-1", ACTION_INSERT, "policy_created", {"version": 2})
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "relocation_policy")
        self.assertEqual(kw["entity_id"], "pol-1")
        self.assertEqual(kw["action_type"], ACTION_INSERT)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["actor_id"], "hr-5")
        self.assertEqual(kw["new_value"]["event"], "policy_created")
        self.assertEqual(kw["new_value"]["version"], 2)
        session.commit.assert_called_once()

    def test_activate_audited(self):
        ctx, audit, _ = _patch()
        with ctx:
            hr_policies._audit_policy(USER, "pol-1", ACTION_UPDATE, "policy_activated", {"version": 3})
        self.assertEqual(audit.call_args.kwargs["action_type"], ACTION_UPDATE)
        self.assertEqual(audit.call_args.kwargs["new_value"]["event"], "policy_activated")

    def test_audit_is_failsoft(self):
        ctx, audit, _ = _patch()
        audit.side_effect = RuntimeError("db down")
        with ctx:
            hr_policies._audit_policy(USER, "pol-1", ACTION_UPDATE, "policy_updated")


if __name__ == "__main__":
    unittest.main()
