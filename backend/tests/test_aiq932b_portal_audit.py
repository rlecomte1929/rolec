"""
AIQ-932b (slice 2) — canonical audit_logs for vendor-portal writes.

provider_portal task-update and profile-update are vendor-initiated (provider
JWT) and write via the Supabase client; events_tracker.track() is analytics, not
a durable audit. A canonical audit_logs row is written fail-soft in a dedicated
SessionLocal txn, with the vendor's provider_id as the actor.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **k: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from backend.app.routers import provider_portal as portal  # noqa: E402
from backend.app.services.audit_log_service import ACTION_UPDATE, ACTOR_HUMAN  # noqa: E402


def _patch():
    session = MagicMock()
    sl = MagicMock()
    sl.return_value.__enter__.return_value = session
    audit = MagicMock()
    return patch.multiple(portal, SessionLocal=sl, insert_audit_log=audit), audit, session


class TestPortalAudit(unittest.TestCase):
    def test_task_update_actor_is_vendor(self):
        ctx, audit, session = _patch()
        with ctx:
            portal._audit_portal("vendor-1", "provider_task", "t-9",
                                 "provider_task_updated_by_vendor", {"status": "completed"})
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "provider_task")
        self.assertEqual(kw["entity_id"], "t-9")
        self.assertEqual(kw["action_type"], ACTION_UPDATE)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["actor_id"], "vendor-1")
        self.assertEqual(kw["new_value"]["event"], "provider_task_updated_by_vendor")
        self.assertEqual(kw["new_value"]["by"], "provider")
        self.assertEqual(kw["new_value"]["status"], "completed")
        session.commit.assert_called_once()

    def test_profile_update_audited(self):
        ctx, audit, _ = _patch()
        with ctx:
            portal._audit_portal("vendor-1", "provider", "vendor-1",
                                 "provider_profile_updated_by_vendor")
        self.assertEqual(audit.call_args.kwargs["entity_type"], "provider")
        self.assertEqual(audit.call_args.kwargs["new_value"]["event"],
                         "provider_profile_updated_by_vendor")

    def test_audit_is_failsoft(self):
        ctx, audit, _ = _patch()
        audit.side_effect = RuntimeError("db down")
        with ctx:
            portal._audit_portal("vendor-1", "provider_task", "t-9", "provider_task_updated_by_vendor")


if __name__ == "__main__":
    unittest.main()
