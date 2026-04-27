"""
Tests for backend/services/employee_demand.py — Phase 2 notifications.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services import employee_demand  # noqa: E402


SCHEMA = """
CREATE TABLE catalog_employee_demand (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    category TEXT NOT NULL,
    destination_city TEXT,
    destination_country TEXT,
    last_seen_by_user_id TEXT,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    demand_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, category, destination_city)
);
"""


class EmployeeDemandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        patcher = mock.patch.object(employee_demand.db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_first_record_creates_row(self) -> None:
        company = str(uuid.uuid4())
        emp = str(uuid.uuid4())
        employee_demand.record_demand(
            company_id=company, category="schools",
            destination_city="Tokyo", destination_country="Japan",
            employee_user_id=emp,
        )
        rows = employee_demand.list_demand_for_company(company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "schools")
        self.assertEqual(rows[0]["destination_city"], "Tokyo")
        self.assertEqual(rows[0]["demand_count"], 1)
        self.assertEqual(rows[0]["last_seen_by_user_id"], emp)

    def test_repeat_increments_count(self) -> None:
        company = str(uuid.uuid4())
        for _ in range(5):
            employee_demand.record_demand(
                company_id=company, category="schools", destination_city="Tokyo",
            )
        rows = employee_demand.list_demand_for_company(company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["demand_count"], 5)

    def test_distinct_combos_get_distinct_rows(self) -> None:
        company = str(uuid.uuid4())
        for cat in ("schools", "movers", "schools"):
            employee_demand.record_demand(
                company_id=company, category=cat, destination_city="Tokyo",
            )
        rows = employee_demand.list_demand_for_company(company)
        self.assertEqual(len(rows), 2)
        cats = {r["category"]: r["demand_count"] for r in rows}
        self.assertEqual(cats["schools"], 2)
        self.assertEqual(cats["movers"], 1)

    def test_tenant_scoped(self) -> None:
        co_a, co_b = str(uuid.uuid4()), str(uuid.uuid4())
        employee_demand.record_demand(company_id=co_a, category="schools", destination_city="Tokyo")
        employee_demand.record_demand(company_id=co_b, category="movers", destination_city="Berlin")
        self.assertEqual(len(employee_demand.list_demand_for_company(co_a)), 1)
        self.assertEqual(len(employee_demand.list_demand_for_company(co_b)), 1)

    def test_empty_company_or_category_no_op(self) -> None:
        # Defensive — never crash on bad inputs.
        employee_demand.record_demand(company_id="", category="schools", destination_city="Tokyo")
        employee_demand.record_demand(company_id=str(uuid.uuid4()), category="", destination_city="Tokyo")
        # Nothing recorded for either.
        with self.engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM catalog_employee_demand")).scalar()
        self.assertEqual(n, 0)

    def test_country_back_filled_on_repeat(self) -> None:
        # First record without country, second with — country should land
        # on the existing row instead of being lost.
        company = str(uuid.uuid4())
        employee_demand.record_demand(
            company_id=company, category="schools", destination_city="Tokyo",
        )
        employee_demand.record_demand(
            company_id=company, category="schools", destination_city="Tokyo",
            destination_country="Japan",
        )
        rows = employee_demand.list_demand_for_company(company)
        self.assertEqual(rows[0]["destination_country"], "Japan")
        self.assertEqual(rows[0]["demand_count"], 2)


if __name__ == "__main__":
    unittest.main()
