"""
Regression tests for GET /api/cases/{case_id}/vendors (list_case_vendors).

[AIQ-1011 / AUDIT-2026-06-13-VENDORS] The endpoint 500'd because its SELECT
referenced columns absent from the deployed schema (cvs.status,
cvs.contact_name, cvs.contact_email, v.website). These tests reconstruct the
real schema in sqlite — under a `public` schema so the production
public.-qualified SQL runs unmodified — and assert the endpoint returns 200
with rows that conform to the frontend VendorRow contract for both empty and
populated shortlists.

Direct-call pattern (same as test_services_state_router.py) — bypasses the
FastAPI app wiring and stubs _assert_case_access so tenant enforcement is
exercised independently of this query.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases_read as router_module  # noqa: E402
from backend.app.routers.cases_read import list_case_vendors  # noqa: E402

# Mirror of the ACTUAL deployed schema (verified against prod information_schema
# 2026-06-13), created under a "public" schema so the router's public.-qualified
# SQL runs as-is. NB: vendors has website_url + email (no `contact_email`); the
# per-case contact + status live on case_vendor_shortlist. The previous version
# of this test encoded the inverse — which is why it passed CI while the route
# still 500'd in prod.
SCHEMA = """
CREATE TABLE public.vendors (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  website_url TEXT,
  email TEXT,
  logo_url TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT
);
CREATE TABLE public.case_vendor_shortlist (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  service_key TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  selected INTEGER NOT NULL DEFAULT 1,
  status TEXT,
  contact_name TEXT,
  contact_email TEXT,
  created_at TEXT
);
"""

# The contract the frontend VendorRow type expects (CaseVendorsPanel.tsx).
EXPECTED_KEYS = {
    "shortlist_id",
    "category",
    "status",
    "contact_name",
    "contact_email",
    "vendor_name",
    "vendor_website",
}

_HR_USER = {"id": str(uuid.uuid4()), "role": "HR", "is_admin": False}


def _make_public_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_public(dbapi_conn, _record):  # noqa: ANN001
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS public")

    return engine


class ListCaseVendorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _make_public_engine()
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        self.engine_patcher = mock.patch.object(
            router_module.main_db, "engine", self.engine
        )
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

        # _assert_case_access does the tenant check; exercise the query in
        # isolation by stubbing it to a no-op (authorized).
        self.access_patcher = mock.patch.object(
            router_module, "_assert_case_access", return_value=None
        )
        self.access_patcher.start()
        self.addCleanup(self.access_patcher.stop)

    def _seed_vendor(self, name, website_url="https://vendor.example"):
        vid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.vendors (id, name, website_url) "
                    "VALUES (:id, :n, :w)"
                ),
                {"id": vid, "n": name, "w": website_url},
            )
        return vid

    def _seed_shortlist(self, case_id, vendor_id, service_key="housing", selected=1,
                        status=None, contact_name=None, contact_email=None):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.case_vendor_shortlist "
                    "(id, case_id, service_key, vendor_id, selected, status, contact_name, contact_email) "
                    "VALUES (:id, :c, :sk, :v, :sel, :st, :cn, :ce)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "c": case_id,
                    "sk": service_key,
                    "v": vendor_id,
                    "sel": selected,
                    "st": status,
                    "cn": contact_name,
                    "ce": contact_email,
                },
            )

    def test_empty_shortlist_returns_empty_list_not_500(self) -> None:
        result = list_case_vendors(case_id=str(uuid.uuid4()), user=_HR_USER)
        self.assertEqual(result, [])

    def test_populated_shortlist_rows_conform_to_contract(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Acme Movers", website_url="https://acme.example")
        self._seed_shortlist(
            case_id, vid, service_key="moving", selected=1,
            status="Assigned", contact_name="Ops Team", contact_email="ops@acme.com",
        )

        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 1)
        row = result[0]
        # Every contract key is present — no more, no less.
        self.assertEqual(set(row.keys()), EXPECTED_KEYS)
        self.assertEqual(row["category"], "moving")
        self.assertEqual(row["vendor_name"], "Acme Movers")
        # Real per-case + vendor columns now flow through (the #701 regression).
        self.assertEqual(row["contact_email"], "ops@acme.com")
        self.assertEqual(row["contact_name"], "Ops Team")
        self.assertEqual(row["status"], "Assigned")
        self.assertEqual(row["vendor_website"], "https://acme.example")
        self.assertTrue(row["shortlist_id"])

    def test_status_falls_back_to_selected_when_null(self) -> None:
        # No explicit status on the row → derive from the `selected` flag.
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Old Vendor")
        self._seed_shortlist(case_id, vid, selected=0, status=None)
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "Removed")

    def test_multiple_rows_each_conform(self) -> None:
        case_id = str(uuid.uuid4())
        v1 = self._seed_vendor("Bank A")
        v2 = self._seed_vendor("School B")
        self._seed_shortlist(case_id, v1, service_key="banking")
        self._seed_shortlist(case_id, v2, service_key="school")
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 2)
        for row in result:
            self.assertEqual(set(row.keys()), EXPECTED_KEYS)


if __name__ == "__main__":
    unittest.main()
