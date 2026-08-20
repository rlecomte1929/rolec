"""
Regression tests for the case vendor shortlist — read + write.

[AIQ-1896] Two defects, one journey:

  (a) the READ joined vendor identity from public.suppliers, whose `vendor_id` is
      populated on only 6 of 116 prod rows — so 3 of the 9 live shortlist rows (all
      `housing`) rendered a BLANK supplier name. Vendor identity now comes from
      public.vendors_legacy, the same registry the HR browse directory lists, whose
      `id` is uuid-to-uuid with case_vendor_shortlist.vendor_id (9/9 resolve).
      `test_housing_row_resolves_via_vendors_legacy_not_suppliers` is the
      discriminating case: it seeds exactly the prod shape (a supplier row with a
      NULL vendor_id) and FAILS against the old suppliers join.

  (b) case_vendor_shortlist had NO writer at all — its rows were seeded demo data,
      newest 2026-05-27. cases_write.assign_case_vendor / unassign_case_vendor are
      that missing write path; the `AssignCaseVendorTests` /
      `UnassignCaseVendorTests` classes below cover them.

[AIQ-1646] history: public.vendors was DROPPED in the platform redesign, which is
why the original `JOIN public.vendors` 500'd. vendors_legacy IS that table under its
post-AIQ-1638 name, so this repoint restores the original join key rather than
inventing a new one.

[AIQ-1011 / AUDIT-2026-06-13-VENDORS] history: the per-case contact + status live on
case_vendor_shortlist; vendor name/website come from the joined registry.

Direct-call pattern (same as test_services_state_router.py) — bypasses the FastAPI
app wiring and stubs _assert_case_access so tenant enforcement is exercised
independently of these queries.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from fastapi import HTTPException, Response
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import cases_read as router_module  # noqa: E402
from backend.app.routers import cases_write as write_module  # noqa: E402
from backend.app.routers.cases_read import list_case_vendors  # noqa: E402
from backend.app.routers.cases_write import (  # noqa: E402
    _VendorAssignBody,
    assign_case_vendor,
    unassign_case_vendor,
)

# The live schema, reconstructed. public.suppliers is created too — and deliberately
# left with NULL vendor_id on the housing vendor — because that is the prod shape the
# old join broke on. A fixture that populated suppliers.vendor_id for every vendor
# would NOT reproduce the bug, which was the prior gap.
SCHEMA = """
CREATE TABLE public.suppliers (
  id TEXT PRIMARY KEY,
  vendor_id TEXT,
  name TEXT NOT NULL,
  website TEXT,
  status TEXT,
  created_at TEXT
);
CREATE TABLE public.vendors_legacy (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT,
  website_url TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
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
_ADMIN_USER = {"id": str(uuid.uuid4()), "role": "ADMIN", "is_admin": True}
_EMPLOYEE_USER = {"id": str(uuid.uuid4()), "role": "EMPLOYEE", "is_admin": False}


class _ResponseSpy:
    """Stand-in for the FastAPI-injected Response in direct-call tests.

    Starts with no status_code so "the handler did not override it" is
    distinguishable from "the handler set 200" — a real Response() defaults to
    200 and collapses those two cases.
    """

    def __init__(self) -> None:
        self.status_code = None


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


class _VendorShortlistFixture(unittest.TestCase):
    """Shared in-memory fixture + seeders for both the read and write suites."""

    #: which router module the subclass patches (`main_db.engine` lives on both)
    patched_modules = (router_module,)

    def setUp(self) -> None:
        self.engine = _make_public_engine()
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))

        for mod in self.patched_modules:
            engine_patcher = mock.patch.object(mod.main_db, "engine", self.engine)
            engine_patcher.start()
            self.addCleanup(engine_patcher.stop)

            # _assert_case_access does the tenant check; exercise the queries in
            # isolation by stubbing it to a no-op (authorized).
            access_patcher = mock.patch.object(
                mod, "_assert_case_access", return_value=None
            )
            access_patcher.start()
            self.addCleanup(access_patcher.stop)

            # AIQ-1704: these handlers resolve the (possibly assignment) path id to
            # the canonical case id before their SQL. That resolution is covered by
            # test_resolve_case_ids / test_case_id_resolution_a2; here we exercise
            # the vendor queries in isolation, so stub it to pass the id through
            # unchanged (these fixtures seed no case_assignments row).
            resolve_patcher = mock.patch.object(
                mod, "_canonical_case_id_or_404", side_effect=lambda cid: cid
            )
            resolve_patcher.start()
            self.addCleanup(resolve_patcher.stop)

    def _seed_vendor(
        self,
        name,
        category="Housing Search",
        website="https://vendor.example",
        is_active=1,
        also_in_suppliers=False,
    ):
        """Insert a vendors_legacy row; return its id (the value the shortlist
        references — on prod cvs.vendor_id and vendors_legacy.id are both uuid).

        ``also_in_suppliers`` mirrors the 6-of-116 prod rows that DO carry a
        supplier link. Left False by default: that is the majority prod shape, and
        the shape the old suppliers join failed on.
        """
        vendor_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.vendors_legacy "
                    "(id, name, category, website_url, is_active) "
                    "VALUES (:id, :n, :c, :w, :a)"
                ),
                {"id": vendor_id, "n": name, "c": category, "w": website, "a": is_active},
            )
            conn.execute(
                text(
                    "INSERT INTO public.suppliers (id, vendor_id, name, website) "
                    "VALUES (:id, :vid, :n, :w)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "vid": vendor_id if also_in_suppliers else None,
                    "n": name,
                    "w": website,
                },
            )
        return vendor_id

    def _seed_shortlist(self, case_id, vendor_id, service_key="housing", selected=1,
                        status=None, contact_name=None, contact_email=None):
        row_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.case_vendor_shortlist "
                    "(id, case_id, service_key, vendor_id, selected, status, contact_name, contact_email) "
                    "VALUES (:id, :c, :sk, :v, :sel, :st, :cn, :ce)"
                ),
                {
                    "id": row_id,
                    "c": case_id,
                    "sk": service_key,
                    "v": vendor_id,
                    "sel": selected,
                    "st": status,
                    "cn": contact_name,
                    "ce": contact_email,
                },
            )
        return row_id

    def _shortlist_rows(self, case_id):
        with self.engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT * FROM public.case_vendor_shortlist WHERE case_id = :c "
                    "ORDER BY service_key"
                ),
                {"c": case_id},
            ).mappings().all()


class ListCaseVendorsTests(_VendorShortlistFixture):
    def test_empty_shortlist_returns_empty_list_not_500(self) -> None:
        # AIQ-1646 criterion 4: 200 (empty array), not a 500, on a case with no shortlist.
        result = list_case_vendors(case_id=str(uuid.uuid4()), user=_HR_USER)
        self.assertEqual(result, [])

    def test_housing_row_resolves_via_vendors_legacy_not_suppliers(self) -> None:
        """AIQ-1896 — THE discriminating test.

        Seeds the exact prod shape of the three broken `housing` rows: the vendor
        exists in vendors_legacy, and its suppliers row carries a NULL vendor_id
        (110 of 116 prod supplier rows do). Under the old
        `LEFT JOIN public.suppliers ON s.vendor_id = cvs.vendor_id` this returns
        vendor_name=None — the blank name HR actually saw. It passes only because
        the join now reads vendors_legacy.
        """
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor(
            "NestFinders Europe",
            category="Housing Search",
            website="https://nestfinders.example",
            also_in_suppliers=False,   # ← the prod majority: no supplier link
        )
        self._seed_shortlist(case_id, vid, service_key="housing", status="Assigned")

        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["vendor_name"], "NestFinders Europe")
        self.assertEqual(result[0]["vendor_website"], "https://nestfinders.example")

    def test_populated_shortlist_rows_conform_to_contract(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor(
            "Acme Movers", category="Moving & Freight", website="https://acme.example",
        )
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
        # Vendor identity comes from the vendors_legacy join (AIQ-1896).
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
        vid = self._seed_vendor("Old Vendor")
        self._seed_shortlist(case_id, vid, selected=0, status=None)
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "Removed")

    def test_shortlist_row_with_no_matching_vendor_still_returns_200(self) -> None:
        # A shortlist row whose vendor_id matches no registry row must NOT 500 —
        # the LEFT JOIN keeps the row; vendor name/website come back NULL.
        case_id = str(uuid.uuid4())
        self._seed_shortlist(case_id, str(uuid.uuid4()), service_key="banking", selected=1)
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0].keys()), EXPECTED_KEYS)
        self.assertIsNone(result[0]["vendor_name"])

    def test_multiple_rows_each_conform(self) -> None:
        case_id = str(uuid.uuid4())
        v1 = self._seed_vendor("Bank A", category="Banking Setup")
        v2 = self._seed_vendor("School B", category="School Search")
        self._seed_shortlist(case_id, v1, service_key="banking")
        self._seed_shortlist(case_id, v2, service_key="school")
        result = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(result), 2)
        for row in result:
            self.assertEqual(set(row.keys()), EXPECTED_KEYS)


class AssignCaseVendorTests(_VendorShortlistFixture):
    """AIQ-1896 — POST /api/cases/{case_id}/vendors, the previously missing writer."""

    patched_modules = (router_module, write_module)

    def _assign(self, case_id, user=_HR_USER, **body):
        # A bare Response() already carries 200, which would make "created → 201"
        # look asserted when nothing set it. FastAPI applies the decorator's
        # status_code=201 only when the handler leaves the injected response
        # alone, so spy on that: status_code stays None on create, and the
        # handler sets it to 200 on the idempotent re-post. The real wire codes
        # are pinned app-mounted in AssignCaseVendorRouteTests below.
        response = _ResponseSpy()
        result = assign_case_vendor(
            case_id=case_id,
            body=_VendorAssignBody(**body),
            response=response,
            user=user,
        )
        return result, response

    def test_assign_inserts_a_shortlist_row(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("BerlinReloc GmbH", category="Housing Search")

        self.assertEqual(len(self._shortlist_rows(case_id)), 0)
        result, response = self._assign(case_id, vendor_id=vid)

        rows = self._shortlist_rows(case_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vendor_id"], vid)
        self.assertEqual(rows[0]["status"], "Assigned")
        # Untouched → FastAPI applies the route's 201.
        self.assertIsNone(response.status_code)
        # The POST result is shaped exactly like a GET row, so the client can put it
        # straight into the panel's cache.
        self.assertEqual(set(result.keys()), EXPECTED_KEYS)
        self.assertEqual(result["vendor_name"], "BerlinReloc GmbH")

    def test_assigned_vendor_appears_in_the_case_panel(self) -> None:
        """The end-to-end contract: what POST writes, GET reads back."""
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor(
            "Fragomen Worldwide", category="Immigration Legal",
            website="https://fragomen.example",
        )
        self._assign(case_id, vendor_id=vid, contact_name="Case Team",
                     contact_email="team@fragomen.example")

        listed = list_case_vendors(case_id=case_id, user=_HR_USER)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["vendor_name"], "Fragomen Worldwide")
        self.assertEqual(listed[0]["vendor_website"], "https://fragomen.example")
        self.assertEqual(listed[0]["category"], "immigration")
        self.assertEqual(listed[0]["contact_name"], "Case Team")
        self.assertEqual(listed[0]["status"], "Assigned")

    def test_service_key_derived_from_vendor_category(self) -> None:
        case_id = str(uuid.uuid4())
        for category, expected in [
            ("Housing Search", "housing"),
            ("Immigration Legal", "immigration"),
            ("Moving & Freight", "moving"),
            ("Tax Advisory", "tax"),
            ("Banking Setup", "banking"),
            ("School Search", "school"),
        ]:
            vid = self._seed_vendor(f"V-{expected}", category=category)
            result, _ = self._assign(case_id, vendor_id=vid)
            self.assertEqual(result["category"], expected, category)

    def test_explicit_service_key_overrides_the_derived_one(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Multi-service Co", category="Housing Search")
        result, _ = self._assign(case_id, vendor_id=vid, service_key="destination")
        self.assertEqual(result["category"], "destination")

    def test_reassigning_the_same_vendor_is_idempotent(self) -> None:
        # No unique index exists on (case_id, vendor_id, service_key), so the guard
        # is in the handler: a second POST returns the SAME row with 200, never a
        # duplicate the panel would render twice.
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("SIRVA Worldwide", category="Moving & Freight")

        first, first_response = self._assign(case_id, vendor_id=vid)
        second, second_response = self._assign(case_id, vendor_id=vid)

        self.assertEqual(len(self._shortlist_rows(case_id)), 1)
        self.assertEqual(first["shortlist_id"], second["shortlist_id"])
        self.assertIsNone(first_response.status_code)      # → 201 Created
        self.assertEqual(second_response.status_code, 200)  # → 200, not a duplicate

    def test_same_vendor_under_a_different_service_key_is_a_separate_row(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Full-service Reloc", category="Housing Search")
        self._assign(case_id, vendor_id=vid)
        self._assign(case_id, vendor_id=vid, service_key="destination")
        self.assertEqual(len(self._shortlist_rows(case_id)), 2)

    def test_unknown_vendor_404s(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._assign(str(uuid.uuid4()), vendor_id=str(uuid.uuid4()))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_malformed_vendor_id_404s_rather_than_500s(self) -> None:
        # On Postgres an unguarded `WHERE id = :vid` would raise
        # "invalid input syntax for type uuid" and surface as a 500.
        with self.assertRaises(HTTPException) as ctx:
            self._assign(str(uuid.uuid4()), vendor_id="not-a-uuid")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_inactive_vendor_404s(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Retired Vendor", is_active=0)
        with self.assertRaises(HTTPException) as ctx:
            self._assign(case_id, vendor_id=vid)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(len(self._shortlist_rows(case_id)), 0)

    def test_empty_vendor_id_422s(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._assign(str(uuid.uuid4()), vendor_id="   ")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_employee_cannot_assign_a_vendor_to_their_own_case(self) -> None:
        # _assert_case_access alone admits the case's own employee (correct for
        # reads); assigning a vendor is an HR action, so the handler gates again.
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Self-serve Movers", category="Moving & Freight")
        with self.assertRaises(HTTPException) as ctx:
            self._assign(case_id, user=_EMPLOYEE_USER, vendor_id=vid)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(len(self._shortlist_rows(case_id)), 0)

    def test_admin_may_assign(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Admin-added Vendor")
        self._assign(case_id, user=_ADMIN_USER, vendor_id=vid)
        self.assertEqual(len(self._shortlist_rows(case_id)), 1)


class UnassignCaseVendorTests(_VendorShortlistFixture):
    """AIQ-1896 — DELETE /api/cases/{case_id}/vendors/{shortlist_id}."""

    patched_modules = (router_module, write_module)

    def test_unassign_removes_the_row_from_the_panel(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Temp Vendor")
        row_id = self._seed_shortlist(case_id, vid)

        self.assertEqual(len(list_case_vendors(case_id=case_id, user=_HR_USER)), 1)
        response = unassign_case_vendor(
            case_id=case_id, shortlist_id=row_id, user=_HR_USER
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(list_case_vendors(case_id=case_id, user=_HR_USER), [])

    def test_unknown_shortlist_id_404s(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            unassign_case_vendor(
                case_id=str(uuid.uuid4()),
                shortlist_id=str(uuid.uuid4()),
                user=_HR_USER,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_cannot_unassign_a_row_belonging_to_another_case(self) -> None:
        # The DELETE is scoped by case_id as well as id, so a shortlist id from a
        # case the caller can reach must not be removable through a different case.
        case_a, case_b = str(uuid.uuid4()), str(uuid.uuid4())
        vid = self._seed_vendor("Other Case Vendor")
        row_in_a = self._seed_shortlist(case_a, vid)

        with self.assertRaises(HTTPException) as ctx:
            unassign_case_vendor(
                case_id=case_b, shortlist_id=row_in_a, user=_HR_USER
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(len(self._shortlist_rows(case_a)), 1)

    def test_employee_cannot_unassign(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Protected Vendor")
        row_id = self._seed_shortlist(case_id, vid)
        with self.assertRaises(HTTPException) as ctx:
            unassign_case_vendor(
                case_id=case_id, shortlist_id=row_id, user=_EMPLOYEE_USER
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(len(self._shortlist_rows(case_id)), 1)


class AssignCaseVendorRouteTests(_VendorShortlistFixture):
    """AIQ-1896 — the same two handlers, mounted on the PRODUCTION app.

    Two things only an app-mounted test can prove:
      1. the routes are actually reachable on `backend.main:app` — the instance
         Render boots. A router registered in backend/app/main.py alone returns
         405 in production (CLAUDE.md, "Routers must be registered in BOTH"); the
         direct-call tests above would stay green through that failure.
      2. the real wire status codes (201 created / 200 idempotent / 204 deleted),
         which come from the route decorators, not from the handler bodies.

    Auth is overridden via `backend.app.auth_deps.get_current_user` — the identity
    the routers actually depend on. backend/main.py defines a SECOND, different
    get_current_user, and an override keyed to that one silently never fires.
    """

    patched_modules = (router_module, write_module)

    def setUp(self) -> None:
        super().setUp()
        from fastapi.testclient import TestClient

        from backend.app.auth_deps import get_current_user
        from backend.main import app

        self.app = app
        self.current_user = dict(_HR_USER)
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.addCleanup(app.dependency_overrides.pop, get_current_user, None)
        self.client = TestClient(app)

    def test_routes_are_reachable_on_the_production_app(self) -> None:
        paths = {
            (tuple(sorted(r.methods)), r.path)
            for r in self.app.routes
            if getattr(r, "path", "").startswith("/api/cases/{case_id}/vendors")
        }
        self.assertIn((("GET",), "/api/cases/{case_id}/vendors"), paths)
        self.assertIn((("POST",), "/api/cases/{case_id}/vendors"), paths)
        self.assertIn(
            (("DELETE",), "/api/cases/{case_id}/vendors/{shortlist_id}"), paths
        )

    def test_assign_then_reassign_then_unassign_over_http(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("HTTP Movers", category="Moving & Freight")

        created = self.client.post(
            f"/api/cases/{case_id}/vendors", json={"vendor_id": vid}
        )
        self.assertEqual(created.status_code, 201, created.text)
        shortlist_id = created.json()["shortlist_id"]

        # Idempotent re-post: 200 and the SAME row, not a second one.
        again = self.client.post(
            f"/api/cases/{case_id}/vendors", json={"vendor_id": vid}
        )
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()["shortlist_id"], shortlist_id)

        listed = self.client.get(f"/api/cases/{case_id}/vendors")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["vendor_name"], "HTTP Movers")

        removed = self.client.delete(
            f"/api/cases/{case_id}/vendors/{shortlist_id}"
        )
        self.assertEqual(removed.status_code, 204, removed.text)
        self.assertEqual(self.client.get(f"/api/cases/{case_id}/vendors").json(), [])

    def test_employee_is_refused_over_http(self) -> None:
        case_id = str(uuid.uuid4())
        vid = self._seed_vendor("Refused Vendor")
        self.current_user.clear()
        self.current_user.update(_EMPLOYEE_USER)

        refused = self.client.post(
            f"/api/cases/{case_id}/vendors", json={"vendor_id": vid}
        )
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertEqual(len(self._shortlist_rows(case_id)), 0)


if __name__ == "__main__":
    unittest.main()
