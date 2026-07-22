"""[AIQ-1669] GET /api/hr/cases/{case_id}/rfqs — the HR read of the CANONICAL `rfqs`
table (what the employee actually writes), which no HR surface read before.

Drives the sync handler directly against a sqlite mirror of the columns the query
touches (same pattern as test_hr_rfq_list.py). Covers: (1) an employee-submitted RFQ
becomes visible to HR reading `rfqs`; (2) cross-tenant access 404s without leaking; (3)
a case with no RFQ returns an empty list rather than erroring.
"""
from __future__ import annotations

import unittest
import uuid
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text

from backend.app.routers import hr_coordination as router_module

# Minimal sqlite mirror of the columns get_case_rfqs reads.
SCHEMA = """
CREATE TABLE relocation_cases (id TEXT PRIMARY KEY, company_id TEXT);
CREATE TABLE cases (id TEXT PRIMARY KEY, company_id TEXT);
CREATE TABLE rfqs (
  id TEXT PRIMARY KEY, rfq_ref TEXT, case_id TEXT, status TEXT, created_at TEXT
);
CREATE TABLE rfq_items (id TEXT PRIMARY KEY, rfq_id TEXT, service_key TEXT);
CREATE TABLE rfq_recipients (
  id TEXT PRIMARY KEY, rfq_id TEXT, vendor_id TEXT, status TEXT, last_activity_at TEXT
);
CREATE TABLE suppliers (id TEXT PRIMARY KEY, name TEXT);
"""


class HrCaseRfqsTests(unittest.TestCase):
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

        self.org_id = str(uuid.uuid4())
        self.case_id = str(uuid.uuid4())
        self.user = {"id": "seed-hr-testingapril", "role": "HR"}

    def _seed(self) -> str:
        """Seed a case owned by our org + one employee RFQ with 2 items and 2 recipients."""
        rfq_id = str(uuid.uuid4())
        sup_a, sup_b = str(uuid.uuid4()), str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, :o)"),
                {"c": self.case_id, "o": self.org_id},
            )
            conn.execute(
                text("INSERT INTO suppliers (id, name) VALUES (:a, 'Santa Fe Relocation'), (:b, 'Acme Movers')"),
                {"a": sup_a, "b": sup_b},
            )
            conn.execute(
                text(
                    "INSERT INTO rfqs (id, rfq_ref, case_id, status, created_at) "
                    "VALUES (:id, 'RFQ-1', :c, 'sent', '2026-07-22T00:00:00')"
                ),
                {"id": rfq_id, "c": self.case_id},
            )
            conn.execute(
                text("INSERT INTO rfq_items (id, rfq_id, service_key) VALUES (:i1, :r, 'movers'), (:i2, :r, 'schools')"),
                {"i1": str(uuid.uuid4()), "i2": str(uuid.uuid4()), "r": rfq_id},
            )
            conn.execute(
                text(
                    "INSERT INTO rfq_recipients (id, rfq_id, vendor_id, status, last_activity_at) "
                    "VALUES (:x1, :r, :a, 'sent', NULL), (:x2, :r, :b, 'viewed', NULL)"
                ),
                {"x1": str(uuid.uuid4()), "x2": str(uuid.uuid4()), "r": rfq_id, "a": sup_a, "b": sup_b},
            )
        return rfq_id

    def test_employee_rfq_is_visible_to_hr_from_rfqs(self) -> None:
        rfq_id = self._seed()
        out = router_module.get_case_rfqs(self.case_id, hr_user=self.user, org_id=self.org_id)
        self.assertEqual(len(out["rfqs"]), 1)
        rfq = out["rfqs"][0]
        self.assertEqual(rfq["id"], rfq_id)
        self.assertEqual(rfq["rfq_ref"], "RFQ-1")
        self.assertEqual(rfq["status"], "sent")
        self.assertCountEqual(rfq["service_keys"], ["movers", "schools"])
        self.assertEqual(len(rfq["recipients"]), 2)
        names = {r["supplier_name"] for r in rfq["recipients"]}
        self.assertIn("Santa Fe Relocation", names)

    def test_cross_tenant_access_404s_without_leaking(self) -> None:
        self._seed()
        with self.assertRaises(HTTPException) as ctx:
            router_module.get_case_rfqs(
                self.case_id, hr_user=self.user, org_id=str(uuid.uuid4())  # a different org
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_case_with_no_rfq_returns_empty_list(self) -> None:
        # Case owned by the org but no RFQ submitted yet.
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, :o)"),
                {"c": self.case_id, "o": self.org_id},
            )
        out = router_module.get_case_rfqs(self.case_id, hr_user=self.user, org_id=self.org_id)
        self.assertEqual(out, {"rfqs": []})


if __name__ == "__main__":
    unittest.main()
