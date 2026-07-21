"""
Regression tests for GET /api/cases/{case_id}/vendors (list_case_vendors).

[AIQ-1646] public.vendors was DROPPED in the platform redesign, so the endpoint's
`JOIN public.vendors` 500'd on every HR case-summary load. The fix repoints the
join at public.suppliers (suppliers.vendor_id references the old vendors.id, the
same key case_vendor_shortlist.vendor_id carries). These tests reconstruct the
POST-DROP schema in sqlite — under a `public` schema so the production
public.-qualified SQL runs unmodified, WITHOUT a public.vendors table — so they
actually reproduce the drop and assert 200 + a VendorRow-conformant contract for
both empty and populated shortlists.

[AIQ-1011 / AUDIT-2026-06-13-VENDORS] history: the per-case contact + status live
on case_vendor_shortlist; vendor name/website come from the joined registry.

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

# The POST-DROP schema (AIQ-1646): NO public.vendors. Vendor identity now comes
# from public.suppliers, joined on suppliers.vendor_id = case_vendor_shortlist.vendor_id
# (both hold the old vendors.id). Created under a "public" schema so the router's
# public.-qualified SQL runs as-is. A test that still created public.vendors would
# NOT reproduce the bug (the query would keep working) — that was the prior gap.
SCHEMA = """
CREATE TABLE public.suppliers (
  id TEXT PRIMARY KEY,
  vendor_id TEXT,
  name TEXT NOT NULL,
  website TEXT,
  status TEXT,
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

    def _seed_supplier(self, name, website="https://vendor.example"):
        """Insert a supplier and return its ``vendor_id`` link (the value the
        shortlist row references — mirrors prod, where cvs.vendor_id and
        suppliers.vendor_id both hold the old vendors.id)."""
        vendor_link = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.suppliers (id, vendor_id, name, website) "
                    "VALUES (:id, :vid, :n, :w)"
                ),
                {"id": str(uuid.uuid4()), "vid": vendor_link, "n": name, "w": website},
            )
        return vendor_link

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
        # AIQ-1646 criterion 4: 200 (empty array), not a 500, on a case with no shortlist.
        result = list_case_vendors(case_id=str(uuid.uuid4()), user=_HR_USER)
        self.assertEqual(result, [])

    def test_populated_shortlist_rows_conform_to_contract(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_supplier("Acme Movers", website="https://acme.example")
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
        # Vendor identity now comes from the supplier join (AIQ-1646).
        self.assertEqual(row["vendor_name"], "Acme Movers")
        self.assertEqual(row["vendor_website"], "https://acme.example")
        # Per-case contact + status flow from the shortlist row.
        self.assertEqual(row["contact_email"], "ops@acme.com")
        self.assertEqual(row["contact_name"], "Ops Team")
        self.assertEqual(row["status"], "Assigned")
        self.assertTrue(row["shortlist_id"])

    def test_status_falls_back_to_selected_when_null(self) -> None:
        # No explicit status on the row → derive from the `selected` flag.
        case_id = str(uuid.uuid4())
        vid = self._seed_supplier("Old Vendor")
        self._seed_shortlist(case_id, vid, selected=0, status=None)
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "Removed")

    def test_shortlist_row_with_no_matching_supplier_still_returns_200(self) -> None:
        # AIQ-1646: a shortlist row whose vendor_id has no supplier match must NOT
        # 500 (the LEFT JOIN keeps the row; vendor name/website come back NULL).
        case_id = str(uuid.uuid4())
        self._seed_shortlist(case_id, str(uuid.uuid4()), service_key="banking", selected=1)
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0].keys()), EXPECTED_KEYS)
        self.assertIsNone(result[0]["vendor_name"])

    def test_multiple_rows_each_conform(self) -> None:
        case_id = str(uuid.uuid4())
        v1 = self._seed_supplier("Bank A")
        v2 = self._seed_supplier("School B")
        self._seed_shortlist(case_id, v1, service_key="banking")
        self._seed_shortlist(case_id, v2, service_key="school")
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 2)
        for row in result:
            self.assertEqual(set(row.keys()), EXPECTED_KEYS)


if __name__ == "__main__":
    unittest.main()
