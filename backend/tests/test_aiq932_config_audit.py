"""
AIQ-932 — service-layer canonical audit for config-write routers.

branding (PUT /branding-config) and ab_tests (promote/rollback) write via the
Supabase client / Vercel Edge Config (no SQLAlchemy router conn) and only logged
to analytics tables, so a durable audit_logs row is added in a dedicated txn.
These tests exercise the fail-soft audit helpers directly.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **k: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from backend.app.routers import ab_tests, branding  # noqa: E402
from backend.app.services.audit_log_service import ACTION_UPDATE, ACTOR_HUMAN  # noqa: E402

USER = {"id": "admin-1", "role": "admin"}


def _patch(module):
    """Patch <module>.SessionLocal + insert_audit_log; return (ctx, audit_mock)."""
    session = MagicMock()
    sl = MagicMock()
    sl.return_value.__enter__.return_value = session
    audit = MagicMock()
    return patch.multiple(module, SessionLocal=sl, insert_audit_log=audit), audit, session


class TestBrandingAudit(unittest.TestCase):
    def test_branding_audit_writes_canonical_row(self):
        ctx, audit, session = _patch(branding)
        with ctx:
            branding._audit_branding(USER, "co-9", "branding_config_updated")
        audit.assert_called_once()
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "company_branding")
        self.assertEqual(kw["entity_id"], "co-9")
        self.assertEqual(kw["action_type"], ACTION_UPDATE)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["actor_id"], "admin-1")
        self.assertEqual(kw["new_value"]["event"], "branding_config_updated")
        session.commit.assert_called_once()

    def test_branding_audit_is_failsoft(self):
        ctx, audit, _ = _patch(branding)
        audit.side_effect = RuntimeError("db down")
        with ctx:
            branding._audit_branding(USER, "co-9", "branding_config_updated")  # must not raise


class TestAbTestAudit(unittest.TestCase):
    def test_abtest_audit_writes_canonical_row(self):
        ctx, audit, session = _patch(ab_tests)
        with ctx:
            ab_tests._audit_abtest(USER, "ab_test_promoted", "hero_copy", {"variant": "b"})
        audit.assert_called_once()
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "ab_test_flag")
        self.assertEqual(kw["entity_id"], "hero_copy")
        self.assertEqual(kw["action_type"], ACTION_UPDATE)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["new_value"]["event"], "ab_test_promoted")
        self.assertEqual(kw["new_value"]["variant"], "b")

    def test_abtest_audit_is_failsoft(self):
        ctx, audit, _ = _patch(ab_tests)
        audit.side_effect = RuntimeError("db down")
        with ctx:
            ab_tests._audit_abtest(USER, "ab_test_rolled_back", "hero_copy", {})  # must not raise


if __name__ == "__main__":
    unittest.main()
