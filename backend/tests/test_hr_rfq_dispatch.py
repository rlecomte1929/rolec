"""[AIQ-1670] POST /api/hr/cases/{case_id}/rfqs/{rfq_id}/dispatch — HR-gated dispatch of an
employee-submitted RFQ.

Verifies the endpoint (1) is company-scoped: 404 on a case outside the org and 404 on an
rfq_id that isn't part of the case, WITHOUT dispatching; (2) on the happy path reuses the
audited `dispatch_supplier_links` for every recipient with send_email defaulting OFF (no
auto-email). `resolve_rfq_targets` and `dispatch_supplier_links` are mocked so no real token
is minted / email sent — the unit under test is the routing + tenant scope + reuse contract.
"""
from __future__ import annotations

import unittest
import uuid
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text

from backend.app.routers import hr_coordination as router_module

SCHEMA = """
CREATE TABLE relocation_cases (id TEXT PRIMARY KEY, company_id TEXT);
CREATE TABLE cases (id TEXT PRIMARY KEY, company_id TEXT);
CREATE TABLE rfqs (id TEXT PRIMARY KEY, case_id TEXT);
"""


class HrRfqDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

        # Never touch the real audited dispatch / target resolution in a unit test.
        self.targets = [
            {"recipient_id": "rec-1", "vendor_id": "sup-a", "supplier_name": "Santa Fe", "email": None, "verified": False},
            {"recipient_id": "rec-2", "vendor_id": "sup-b", "supplier_name": "Acme", "email": "ops@acme.test", "verified": True},
        ]
        self.resolve_patcher = mock.patch.object(
            router_module, "resolve_rfq_targets", return_value=self.targets
        )
        self.mock_resolve = self.resolve_patcher.start()
        self.addCleanup(self.resolve_patcher.stop)
        self.dispatch_patcher = mock.patch.object(
            router_module, "dispatch_supplier_links",
            return_value=[{"recipient_id": "rec-1", "ok": True, "sent": False},
                          {"recipient_id": "rec-2", "ok": True, "sent": False}],
        )
        self.mock_dispatch = self.dispatch_patcher.start()
        self.addCleanup(self.dispatch_patcher.stop)
        # Best-effort side effects — keep them out of the unit.
        for name in ("track_event", "insert_audit_log"):
            p = mock.patch.object(router_module, name, lambda *a, **k: None)
            p.start()
            self.addCleanup(p.stop)

        self.org_id = str(uuid.uuid4())
        self.case_id = str(uuid.uuid4())
        self.rfq_id = str(uuid.uuid4())
        self.user = {"id": "seed-hr-testingapril", "role": "HR"}

    def _seed_case_and_rfq(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, :o)"),
                {"c": self.case_id, "o": self.org_id},
            )
            conn.execute(
                text("INSERT INTO rfqs (id, case_id) VALUES (:r, :c)"),
                {"r": self.rfq_id, "c": self.case_id},
            )

    def _body(self, send_email: bool = False):
        return router_module.DispatchRfqBody(send_email=send_email)

    def test_hr_gated_dispatch_reuses_the_audited_path_for_every_recipient(self) -> None:
        self._seed_case_and_rfq()
        out = router_module.dispatch_case_rfq(
            self.case_id, self.rfq_id, self._body(), hr_user=self.user, org_id=self.org_id
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["dispatched"], 2)
        # Reused the audited dispatcher with THIS rfq, its resolved targets, send_email OFF.
        self.mock_dispatch.assert_called_once_with(
            rfq_id=self.rfq_id, targets=self.targets, send_email=False, actor_email=None
        )

    def test_send_email_defaults_off_no_auto_blast(self) -> None:
        self._seed_case_and_rfq()
        router_module.dispatch_case_rfq(
            self.case_id, self.rfq_id, self._body(), hr_user=self.user, org_id=self.org_id
        )
        _, kwargs = self.mock_dispatch.call_args
        self.assertIs(kwargs["send_email"], False)

    def test_cross_tenant_case_404s_and_does_not_dispatch(self) -> None:
        self._seed_case_and_rfq()
        with self.assertRaises(HTTPException) as ctx:
            router_module.dispatch_case_rfq(
                self.case_id, self.rfq_id, self._body(), hr_user=self.user, org_id=str(uuid.uuid4())
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.mock_dispatch.assert_not_called()

    def test_rfq_not_in_case_404s_and_does_not_dispatch(self) -> None:
        # Case belongs to the org, but the rfq_id is not part of it.
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, :o)"),
                {"c": self.case_id, "o": self.org_id},
            )
        with self.assertRaises(HTTPException) as ctx:
            router_module.dispatch_case_rfq(
                self.case_id, str(uuid.uuid4()), self._body(), hr_user=self.user, org_id=self.org_id
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.mock_dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
