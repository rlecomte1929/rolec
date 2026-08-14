"""[AIQ-1672] Company-scope regression for POST /api/hr/rfqs/{rfq_id}/supplier-links.

Before this, `send_supplier_links` loaded the RFQ with no tenant check, so any HR/admin could
mint tokens (and email suppliers) on ANOTHER company's RFQ by enumerating rfq_ids — a
cross-tenant IDOR. These tests drive the sync handler directly against a sqlite mirror and mock
the audited dispatch, asserting: (1) an rfq whose case is outside the caller's org → 404 and the
dispatcher is NOT called; (2) the owning org still dispatches.
"""
from __future__ import annotations

import unittest
import uuid
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text

from backend.app.routers import supplier_rfq as router_module

SCHEMA = """
CREATE TABLE relocation_cases (id TEXT PRIMARY KEY, company_id TEXT);
CREATE TABLE cases (id TEXT PRIMARY KEY, company_id TEXT);
CREATE TABLE rfqs (id TEXT PRIMARY KEY, case_id TEXT);
"""


class SupplierLinksScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))

        self.org_id = str(uuid.uuid4())
        self.case_id = str(uuid.uuid4())
        self.rfq_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, :o)"),
                {"c": self.case_id, "o": self.org_id},
            )
            conn.execute(
                text("INSERT INTO rfqs (id, case_id) VALUES (:r, :c)"),
                {"r": self.rfq_id, "c": self.case_id},
            )

        # db.engine → sqlite; db.get_rfq → truthy (so the pre-existing existence check passes and
        # we exercise the NEW company gate).
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        self.getrfq_patcher = mock.patch.object(
            router_module.db, "get_rfq",
            return_value={"id": self.rfq_id, "rfq_ref": "RFQ-1", "case_id": self.case_id},
        )
        self.getrfq_patcher.start()
        self.addCleanup(self.getrfq_patcher.stop)

        # Never touch the audited resolve/dispatch in a unit test.
        self.resolve_patcher = mock.patch.object(
            router_module, "resolve_rfq_targets",
            return_value=[{"recipient_id": "rec-1", "vendor_id": "v1", "supplier_name": "S",
                           "email": None, "verified": False}],
        )
        self.mock_resolve = self.resolve_patcher.start()
        self.addCleanup(self.resolve_patcher.stop)
        self.dispatch_patcher = mock.patch.object(
            router_module, "dispatch_supplier_links",
            return_value=[{"recipient_id": "rec-1", "ok": True, "sent": False}],
        )
        self.mock_dispatch = self.dispatch_patcher.start()
        self.addCleanup(self.dispatch_patcher.stop)

        self.user = {"id": "seed-hr-testingapril", "role": "HR"}

    def _payload(self):
        return router_module.SendSupplierLinksPayload(
            targets=[router_module.SupplierLinkTarget(recipient_id="rec-1")], send_email=False
        )

    def test_cross_tenant_rfq_404s_and_does_not_dispatch(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            router_module.send_supplier_links(
                self.rfq_id, self._payload(), user=self.user, org_id=str(uuid.uuid4())
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.mock_dispatch.assert_not_called()
        self.mock_resolve.assert_not_called()

    def test_owning_org_still_dispatches(self) -> None:
        out = router_module.send_supplier_links(
            self.rfq_id, self._payload(), user=self.user, org_id=self.org_id
        )
        self.assertTrue(out["ok"])
        self.mock_dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
