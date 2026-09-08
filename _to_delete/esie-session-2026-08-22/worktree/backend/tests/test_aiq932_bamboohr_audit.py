"""
AIQ-932 (slice 3) — canonical audit_logs for BambooHR HRIS connection writes.

connect/disconnect/field-mapping writes go through the Supabase client (no
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

from backend.app.routers import integrations_bamboohr as bamboo  # noqa: E402
from backend.app.services.audit_log_service import (  # noqa: E402
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
)

USER = {"id": "hr-3", "role": "hr"}


def _patch():
    session = MagicMock()
    sl = MagicMock()
    sl.return_value.__enter__.return_value = session
    audit = MagicMock()
    return patch.multiple(bamboo, SessionLocal=sl, insert_audit_log=audit), audit, session


class TestBambooHrAudit(unittest.TestCase):
    def test_connect_insert_audited(self):
        ctx, audit, session = _patch()
        with ctx:
            bamboo._audit_bamboohr(USER, "c-1", ACTION_INSERT, "bamboohr_connected")
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "hris_connection")
        self.assertEqual(kw["entity_id"], "c-1")
        self.assertEqual(kw["action_type"], ACTION_INSERT)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["actor_id"], "hr-3")
        self.assertEqual(kw["new_value"]["event"], "bamboohr_connected")
        self.assertEqual(kw["new_value"]["provider"], "bamboohr")
        session.commit.assert_called_once()

    def test_disconnect_update_audited(self):
        ctx, audit, _ = _patch()
        with ctx:
            bamboo._audit_bamboohr(USER, "c-1", ACTION_UPDATE, "bamboohr_disconnected")
        self.assertEqual(audit.call_args.kwargs["action_type"], ACTION_UPDATE)
        self.assertEqual(audit.call_args.kwargs["new_value"]["event"], "bamboohr_disconnected")

    def test_audit_is_failsoft(self):
        ctx, audit, _ = _patch()
        audit.side_effect = RuntimeError("db down")
        with ctx:
            bamboo._audit_bamboohr(USER, "c-1", ACTION_UPDATE, "bamboohr_field_mappings_updated")


if __name__ == "__main__":
    unittest.main()
