"""
[AIQ-859] Regression: GET /api/hr/rfq-requests 500'd because the vendor join
selected `v.contact_email`, but public.vendors has no such column (it's `email`).
Every call failed with UndefinedColumn → 500.

The handler is async; this repo has no pytest-asyncio, so we drive it with a
plain asyncio.run() inside a normal sync test. With the old `contact_email` SQL,
sqlite raises "no such column" and the test fails; with `v.email` it passes.
"""
from __future__ import annotations

import asyncio
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

from backend.app.routers import hr_rfq as router_module

# Minimal sqlite mirror of the columns the list query touches.
SCHEMA = """
CREATE TABLE vendors (
  id TEXT PRIMARY KEY, name TEXT, email TEXT
);
CREATE TABLE rfq_requests (
  id TEXT PRIMARY KEY, case_id TEXT, vendor_id TEXT, service_category TEXT,
  move_date TEXT, budget_range TEXT, special_requirements TEXT,
  hr_email TEXT, hr_name TEXT, status TEXT, created_at TEXT, updated_at TEXT,
  org_id TEXT
);
"""


class HrRfqListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        self.org_id = str(uuid.uuid4())
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        # _require_hr resolves company/tenant; stub it to our org so the list is scoped.
        self.hr_patcher = mock.patch.object(
            router_module, "_require_hr", return_value=(self.org_id, None, None)
        )
        self.hr_patcher.start()
        self.addCleanup(self.hr_patcher.stop)
        self.user = {"id": "seed-hr-testingapril", "role": "HR"}

    def _seed_rfq(self) -> None:
        vid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO vendors (id, name, email) VALUES (:id, :n, :e)"),
                {"id": vid, "n": "Acme Movers", "e": "ops@acme.test"},
            )
            conn.execute(
                text(
                    "INSERT INTO rfq_requests (id, case_id, vendor_id, status, org_id) "
                    "VALUES (:id, :c, :v, 'pending', :o)"
                ),
                {"id": str(uuid.uuid4()), "c": str(uuid.uuid4()), "v": vid, "o": self.org_id},
            )

    def test_empty_list_returns_200_shape(self) -> None:
        # The original 500 fired even with zero RFQs (column error compiles before rows).
        res = asyncio.run(router_module.list_rfqs(case_id=None, user=self.user))
        self.assertEqual(res, {"rfqs": [], "total": 0})

    def test_list_joins_vendor_email_not_contact_email(self) -> None:
        self._seed_rfq()
        res = asyncio.run(router_module.list_rfqs(case_id=None, user=self.user))
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["rfqs"][0]["vendor_name"], "Acme Movers")
        self.assertEqual(res["rfqs"][0]["vendor_email"], "ops@acme.test")


if __name__ == "__main__":
    unittest.main()
