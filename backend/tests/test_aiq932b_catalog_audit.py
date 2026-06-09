"""
AIQ-932b (slice 3) — canonical audit_logs for HR vendor-curation writes.

bulk_select / add_custom / delete_custom go through vendor_curation, which only
records created_by on the row (no audit_logs). A canonical audit_logs row is
written fail-soft in a dedicated SessionLocal txn. The destination-request
resolve endpoint is NOT covered here — scrape_safety already audits it.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **k: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from backend.app.routers import hr_catalog  # noqa: E402
from backend.app.services.audit_log_service import (  # noqa: E402
    ACTION_DELETE,
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
)


def _patch():
    session = MagicMock()
    sl = MagicMock()
    sl.return_value.__enter__.return_value = session
    audit = MagicMock()
    return patch.multiple(hr_catalog, SessionLocal=sl, insert_audit_log=audit), audit, session


class TestCatalogAudit(unittest.TestCase):
    def test_add_custom_insert(self):
        ctx, audit, session = _patch()
        with ctx:
            hr_catalog._audit_catalog("hr-1", "row-1", ACTION_INSERT, "custom_vendor_added",
                                      {"category": "movers", "name": "Acme"})
        kw = audit.call_args.kwargs
        self.assertEqual(kw["entity_type"], "company_vendor_selection")
        self.assertEqual(kw["entity_id"], "row-1")
        self.assertEqual(kw["action_type"], ACTION_INSERT)
        self.assertEqual(kw["actor_type"], ACTOR_HUMAN)
        self.assertEqual(kw["actor_id"], "hr-1")
        self.assertEqual(kw["new_value"]["event"], "custom_vendor_added")
        self.assertEqual(kw["new_value"]["name"], "Acme")
        session.commit.assert_called_once()

    def test_bulk_update_and_delete(self):
        ctx, audit, _ = _patch()
        with ctx:
            hr_catalog._audit_catalog("hr-1", "co-1", ACTION_UPDATE, "vendor_selections_updated",
                                      {"count": 3})
            hr_catalog._audit_catalog("hr-1", "row-1", ACTION_DELETE, "custom_vendor_deleted")
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(audit.call_args_list[0].kwargs["action_type"], ACTION_UPDATE)
        self.assertEqual(audit.call_args_list[1].kwargs["action_type"], ACTION_DELETE)

    def test_audit_is_failsoft(self):
        ctx, audit, _ = _patch()
        audit.side_effect = RuntimeError("db down")
        with ctx:
            hr_catalog._audit_catalog("hr-1", "row-1", ACTION_INSERT, "custom_vendor_added")


if __name__ == "__main__":
    unittest.main()
