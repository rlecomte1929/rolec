"""
AIQ-932b (slice 1) — canonical audit_logs for provider-domain writes.

create_provider, patch_provider_task, invite_provider, accept_provider_invite
write via the Supabase client (no SQLAlchemy router conn), so a durable
audit_logs row is written in a dedicated SessionLocal txn. create_provider_task
is deliberately NOT audited here — hr_coordination already audits provider_task
creation (avoid double-audit). Exercises the fail-soft helper directly.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **k: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from backend.app.routers import providers  # noqa: E402
from backend.app.services.audit_log_service import (  # noqa: E402
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
)


def _patch():
    session = MagicMock()
    sl = MagicMock()
    sl.return_value.__enter__.return_value = session
    audit = MagicMock()
    return patch.multiple(providers, SessionLocal=sl, insert_audit_log=audit), audit, session


class TestProviderAudit(unittest.TestCase):
    def test_create_provider_audited(self):
        ctx, audit, session = _patch()
        with ctx:
            providers._audit_provider("hr-1", "provider", "p-1", ACTION_INSERT,
                                      "provider_created", {"service_type": "movers"})
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "provider")
        self.assertEqual(kw["entity_id"], "p-1")
        self.assertEqual(kw["action_type"], ACTION_INSERT)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["actor_id"], "hr-1")
        self.assertEqual(kw["new_value"]["event"], "provider_created")
        session.commit.assert_called_once()

    def test_invite_accept_use_invite_entity(self):
        ctx, audit, _ = _patch()
        with ctx:
            providers._audit_provider("vendor-9", "provider_invite", "inv-1", ACTION_UPDATE,
                                      "provider_invite_accepted", {"case_id": "c-1"})
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "provider_invite")
        self.assertEqual(kw["actor_id"], "vendor-9")  # vendor, not an HR user
        self.assertEqual(kw["new_value"]["event"], "provider_invite_accepted")

    def test_audit_is_failsoft(self):
        ctx, audit, _ = _patch()
        audit.side_effect = RuntimeError("db down")
        with ctx:
            providers._audit_provider("hr-1", "provider_task", "t-1", ACTION_UPDATE,
                                      "provider_task_updated", {"status": "completed"})


if __name__ == "__main__":
    unittest.main()
