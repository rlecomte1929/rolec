"""
Regression tests for HR/admin /notification-counts handlers.

The handlers used to call list_demand_for_company / list_destination_requests
and compute counts in Python. list_demand_for_company runs an N+1 vendor_curation
lookup per row; under prod load that exhausted the SQLAlchemy pool. They now
use SQL aggregates. These tests pin the aggregate output to match the old
list-and-count semantics.
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

from backend.app.routers import admin_catalog as admin_router  # noqa: E402
from backend.app.routers import hr_catalog as hr_router  # noqa: E402


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
CREATE TABLE company_vendor_selections (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    category TEXT NOT NULL,
    destination_city TEXT,
    country TEXT,
    master_item_id TEXT,
    custom_item_json TEXT,
    selected INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id TEXT
);
CREATE TABLE catalog_destination_requests (
    id TEXT PRIMARY KEY,
    company_id TEXT,
    city TEXT,
    country TEXT,
    category TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_by_user_id TEXT,
    resolved_by TEXT,
    resolved_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE catalog_destination_allowlist (
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    notes TEXT,
    PRIMARY KEY (city, country)
);
"""


def _user(company_id: str):
    return {
        "id": str(uuid.uuid4()),
        "role": "hr",
        "company": company_id,
        "is_admin": False,
    }


class HrNotificationCountsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        patcher = mock.patch.object(hr_router.db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)
        # _caller_company_id falls back to user["company"] when profile lookup
        # returns no company_id, so stub get_profile_record to return None.
        profile_patcher = mock.patch.object(
            hr_router.db,
            "get_profile_record",
            side_effect=lambda uid: None,
        )
        profile_patcher.start()
        self.addCleanup(profile_patcher.stop)

    def _insert_demand(self, company_id, category, city, count=1):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO catalog_employee_demand "
                    "(id, company_id, category, destination_city, demand_count) "
                    "VALUES (:id, :co, :cat, :city, :n)"
                ),
                {
                    "id": str(uuid.uuid4()), "co": company_id,
                    "cat": category, "city": city, "n": count,
                },
            )

    def _insert_curation(self, company_id, category, city, *, master=True, selected=1, custom=False):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO company_vendor_selections "
                    "(id, company_id, category, destination_city, master_item_id, "
                    " custom_item_json, selected) "
                    "VALUES (:id, :co, :cat, :city, :mid, :custom, :sel)"
                ),
                {
                    "id": str(uuid.uuid4()), "co": company_id,
                    "cat": category, "city": city,
                    "mid": str(uuid.uuid4()) if master else None,
                    "custom": '{"name":"x"}' if custom else None,
                    "sel": selected,
                },
            )

    def _insert_ticket(self, company_id, status):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO catalog_destination_requests "
                    "(id, company_id, status) VALUES (:id, :co, :s)"
                ),
                {"id": str(uuid.uuid4()), "co": company_id, "s": status},
            )

    def test_empty(self):
        company = str(uuid.uuid4())
        result = hr_router.hr_notification_counts(_user(company))
        self.assertEqual(result, {
            "employees_waiting": 0,
            "destinations_with_demand": 0,
            "pending_admin_tickets": 0,
        })

    def test_sums_demand_and_counts_distinct(self):
        company = str(uuid.uuid4())
        self._insert_demand(company, "schools", "Tokyo", count=3)
        self._insert_demand(company, "movers", "Tokyo", count=2)
        self._insert_demand(company, "schools", "Berlin", count=1)
        result = hr_router.hr_notification_counts(_user(company))
        self.assertEqual(result["employees_waiting"], 6)
        self.assertEqual(result["destinations_with_demand"], 3)

    def test_curated_master_selected_hides_demand(self):
        company = str(uuid.uuid4())
        self._insert_demand(company, "schools", "Tokyo", count=4)
        self._insert_demand(company, "movers", "Tokyo", count=2)
        # HR has curated schools/Tokyo → that combo should disappear from counts.
        self._insert_curation(company, "schools", "Tokyo", master=True, selected=1)
        result = hr_router.hr_notification_counts(_user(company))
        self.assertEqual(result["employees_waiting"], 2)  # only movers/Tokyo
        self.assertEqual(result["destinations_with_demand"], 1)

    def test_curated_master_unselected_does_not_hide(self):
        # selected=0 means HR explicitly toggled off — demand should still show.
        company = str(uuid.uuid4())
        self._insert_demand(company, "schools", "Tokyo", count=4)
        self._insert_curation(company, "schools", "Tokyo", master=True, selected=0)
        result = hr_router.hr_notification_counts(_user(company))
        self.assertEqual(result["employees_waiting"], 4)
        self.assertEqual(result["destinations_with_demand"], 1)

    def test_custom_curation_hides_demand(self):
        company = str(uuid.uuid4())
        self._insert_demand(company, "schools", "Tokyo", count=4)
        self._insert_curation(company, "schools", "Tokyo", master=False, custom=True)
        result = hr_router.hr_notification_counts(_user(company))
        self.assertEqual(result["employees_waiting"], 0)
        self.assertEqual(result["destinations_with_demand"], 0)

    def test_curation_with_null_city_hides_geo_agnostic_demand(self):
        # Movers/banks-style: curation row with destination_city NULL covers
        # all cities for that category — matching original _has_curation logic.
        company = str(uuid.uuid4())
        self._insert_demand(company, "movers", "Tokyo", count=2)
        self._insert_demand(company, "movers", "Berlin", count=3)
        self._insert_curation(company, "movers", None, master=True, selected=1)
        result = hr_router.hr_notification_counts(_user(company))
        self.assertEqual(result["employees_waiting"], 0)
        self.assertEqual(result["destinations_with_demand"], 0)

    def test_pending_tickets_scoped_to_company(self):
        co_a = str(uuid.uuid4())
        co_b = str(uuid.uuid4())
        for _ in range(3):
            self._insert_ticket(co_a, "pending")
        self._insert_ticket(co_a, "approved")  # not counted
        self._insert_ticket(co_b, "pending")   # different tenant
        result = hr_router.hr_notification_counts(_user(co_a))
        self.assertEqual(result["pending_admin_tickets"], 3)


class AdminNotificationCountsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        # admin_notification_counts imports db inline; patch the module the
        # router imports from.
        from backend import database as backend_db
        patcher = mock.patch.object(backend_db.db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_counts_pending_and_allowlist(self):
        with self.engine.begin() as conn:
            for status in ("pending", "pending", "approved"):
                conn.execute(
                    text(
                        "INSERT INTO catalog_destination_requests (id, status) "
                        "VALUES (:id, :s)"
                    ),
                    {"id": str(uuid.uuid4()), "s": status},
                )
            for city, country in (("Tokyo", "JP"), ("Berlin", "DE")):
                conn.execute(
                    text(
                        "INSERT INTO catalog_destination_allowlist (city, country) "
                        "VALUES (:c, :co)"
                    ),
                    {"c": city, "co": country},
                )
        user = {"id": "x", "is_admin": True, "role": "admin"}
        result = admin_router.admin_notification_counts(user)
        self.assertEqual(result, {"pending_tickets": 2, "allowlisted_destinations": 2})


if __name__ == "__main__":
    unittest.main()
