"""
Tests for backend/app/routers/exception_requests.py.

Mirrors the pattern in test_admin_router_audit.py: swaps `db.engine` for an
in-memory SQLite engine that has the exception_requests + audit_logs schemas
preloaded, then exercises the router functions directly (bypasses FastAPI's
dependency injection — which keeps the tests independent of the broader
backend.main wiring that other test files break on).
"""
from __future__ import annotations

import os
import re
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import exception_requests as router_module  # noqa: E402
from backend.app.routers.exception_requests import (  # noqa: E402
    ExceptionRequestCreate,
    ExceptionRequestPatch,
    create_exception_request,
    list_exception_requests_for_case,
    list_exception_requests_for_company,
    resolve_exception_request,
)
from fastapi import HTTPException  # noqa: E402


# The live router reads/writes `policy_cap_requests` (renamed from the original
# `exception_requests`) and the Q3-A migration added a NULLABLE `exception_type`
# column. The shared read-back projection (`_EXCEPTION_SELECT_WITH_JOINS`) LEFT
# JOINs profiles / users / mobility_cases / wizard_cases / relocation_cases to
# enrich the row with requester/resolver names + corridor, so those tables must
# exist (empty is fine — LEFT JOIN -> NULL enrichment, which the router tolerates).
SCHEMA = """
CREATE TABLE policy_cap_requests (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  organization_id TEXT NOT NULL,
  category TEXT NOT NULL,
  exception_type TEXT,
  requested_amount REAL NOT NULL,
  cap_amount REAL NOT NULL,
  currency TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  hr_note TEXT,
  requested_by_user_id TEXT NOT NULL,
  resolved_by_user_id TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  old_value_json TEXT,
  new_value_json TEXT,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT
);
CREATE TABLE profiles (
  id TEXT PRIMARY KEY,
  full_name TEXT,
  email TEXT,
  role TEXT
);
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT
);
CREATE TABLE mobility_cases (
  id TEXT PRIMARY KEY,
  origin_country TEXT,
  destination_country TEXT
);
CREATE TABLE wizard_cases (
  id TEXT PRIMARY KEY,
  origin_country TEXT,
  dest_country TEXT
);
CREATE TABLE relocation_cases (
  id TEXT PRIMARY KEY,
  home_country TEXT,
  host_country TEXT
);
"""


def _sqlite_select_with_joins() -> str:
    """SQLite-dialect twin of the router's Postgres `_EXCEPTION_SELECT_WITH_JOINS`.

    The live projection casts the uuid join keys with Postgres' `x::text`
    syntax, which SQLite cannot parse. We translate only that dialect token
    (`x.y::text` -> `CAST(x.y AS TEXT)`) and leave everything else byte-for-byte
    identical, deriving it from the real constant at runtime so this twin can
    never drift out of sync. The Postgres SQL string itself stays under test via
    ExceptionSelectJoinGuardTests.
    """
    from backend.app.routers import exception_requests as _rm

    return re.sub(r"(\w+\.\w+)::text", r"CAST(\1 AS TEXT)", _rm._EXCEPTION_SELECT_WITH_JOINS)


def _company_id():
    return str(uuid.uuid4())


def _make_user(uid: str, role: str, company_id: str, is_admin: bool = False):
    return {
        "id": uid,
        "role": role,
        "company": company_id,
        "is_admin": is_admin,
    }


class ExceptionRequestRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        # Patch both the module-level `db` (used by _audit) AND get_profile_record
        # (used by _caller_company_id when no `company` field is present).
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        self.profile_patcher = mock.patch.object(
            router_module.db,
            "get_profile_record",
            side_effect=lambda uid: {"id": uid, "company_id": None},
        )
        self.profile_patcher.start()
        self.addCleanup(self.profile_patcher.stop)
        # The router reads rows back through a Postgres-only projection
        # (`x::text` casts). Swap in the SQLite-dialect twin so the CRUD/list
        # functions exercise the real INSERT/UPDATE/status/tenant/audit logic
        # against in-memory SQLite.
        self.select_patcher = mock.patch.object(
            router_module, "_EXCEPTION_SELECT_WITH_JOINS", _sqlite_select_with_joins()
        )
        self.select_patcher.start()
        self.addCleanup(self.select_patcher.stop)
        # `require_case_access` (B21) verifies case ownership via assignment
        # tables that aren't part of this unit's SQLite fixture — case-access
        # authz has its own test surface. Stub it so these tests stay focused
        # on the exception-request CRUD/tenant/audit behaviour.
        self.case_access_patcher = mock.patch.object(
            router_module, "require_case_access", return_value={}
        )
        self.case_access_patcher.start()
        self.addCleanup(self.case_access_patcher.stop)
        # backend/conftest.py mocks `backend.database`, so `db` is a MagicMock
        # whose un-patched methods auto-return truthy mocks. Pin the company
        # fallback resolvers to None so the "no company linked" path is
        # deterministic; tests with a company resolve via user["company"] first
        # and never reach these.
        self.hr_company_patcher = mock.patch.object(
            router_module.db, "get_hr_company_id", return_value=None
        )
        self.hr_company_patcher.start()
        self.addCleanup(self.hr_company_patcher.stop)
        self.assignment_patcher = mock.patch.object(
            router_module.db, "get_assignment_for_employee", return_value=None
        )
        self.assignment_patcher.start()
        self.addCleanup(self.assignment_patcher.stop)

    def _audit_rows(self):
        # rowid gives stable insertion order even when multiple rows share
        # second-resolution created_at (datetime.utcnow().isoformat() at the
        # service tier vs. CURRENT_TIMESTAMP defaulting in SQLite both lose
        # sub-second precision on inserts done in the same tick).
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text(
                        "SELECT entity_type, entity_id, action_type, actor_id "
                        "FROM audit_logs ORDER BY rowid"
                    )
                ).mappings()
            )

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------
    def test_create_inserts_row_and_audit(self) -> None:
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        case_id = str(uuid.uuid4())
        body = ExceptionRequestCreate(
            category="housing",
            exception_type="cap_override",
            requested_amount=3500,
            cap_amount=3000,
            currency="eur",
            reason="High-cost city, family of 4 needs 3-bed.",
        )

        result = create_exception_request(case_id=case_id, body=body, user=emp)

        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["category"], "housing")
        self.assertEqual(result["currency"], "EUR")  # uppercased
        self.assertEqual(result["organization_id"], company)
        self.assertEqual(result["requested_by_user_id"], emp["id"])

        # Audit row written
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["entity_type"], "exception_requests")
        self.assertEqual(rows[0]["action_type"], "insert")
        self.assertEqual(rows[0]["actor_id"], emp["id"])

    def test_create_notifies_assigned_hr(self) -> None:
        """[AIQ-1570] The guardrail's missing half: filing an over-cap request must
        tell HR. Before this, the row was written and nobody was told."""
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        case_id = str(uuid.uuid4())
        hr_id = str(uuid.uuid4())
        body = ExceptionRequestCreate(
            category="housing",
            exception_type="cap_override",
            requested_amount=32000,
            cap_amount=25000,
            currency="nok",
            reason="Family of 4, Oslo.",
        )

        with mock.patch.object(
            router_module.db,
            "get_assignment_by_case_id",
            return_value={"id": "assign-1", "hr_user_id": hr_id},
        ), mock.patch.object(
            router_module.db, "create_notification_with_preferences"
        ) as notify:
            create_exception_request(case_id=case_id, body=body, user=emp)

        notify.assert_called_once()
        kwargs = notify.call_args.kwargs
        self.assertEqual(kwargs["user_id"], hr_id)
        self.assertEqual(kwargs["type_"], "POLICY_EXCEPTION_REQUESTED")
        self.assertEqual(kwargs["case_id"], case_id)
        # The amounts HR needs to triage must be in the body, not just metadata.
        self.assertIn("32,000 NOK", kwargs["body"])
        self.assertIn("25,000 NOK", kwargs["body"])
        self.assertEqual(kwargs["metadata"]["exception_type"], "cap_override")

    def test_create_succeeds_when_notification_raises(self) -> None:
        """A broken bell must never cost the employee their request."""
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        body = ExceptionRequestCreate(
            category="housing",
            exception_type="cap_override",
            requested_amount=3500,
            cap_amount=3000,
            currency="eur",
            reason="reason",
        )

        with mock.patch.object(
            router_module.db,
            "get_assignment_by_case_id",
            side_effect=RuntimeError("db down"),
        ):
            result = create_exception_request(
                case_id=str(uuid.uuid4()), body=body, user=emp
            )

        self.assertEqual(result["status"], "pending")

    def test_resolve_notifies_the_employee_in_their_own_currency(self) -> None:
        """The other half of the loop: HR decided, so tell the person who asked — and quote
        the amount in the currency they asked in, not a hardcoded USD."""
        company = _company_id()
        emp_id = str(uuid.uuid4())
        emp = _make_user(emp_id, "EMPLOYEE", company)
        hr = _make_user(str(uuid.uuid4()), "HR", company)
        created = create_exception_request(
            case_id=str(uuid.uuid4()),
            body=ExceptionRequestCreate(
                category="housing",
                exception_type="cap_override",
                requested_amount=32000,
                cap_amount=25000,
                currency="NOK",
                reason="Central Oslo, family of 4.",
            ),
            user=emp,
        )

        with mock.patch.object(
            router_module.db, "create_notification_with_preferences"
        ) as notify:
            resolve_exception_request(
                request_id=created["id"],
                body=ExceptionRequestPatch(status="approved", hr_note="Approved — tight market."),
                user=hr,
            )

        notify.assert_called_once()
        kwargs = notify.call_args.kwargs
        self.assertEqual(kwargs["user_id"], emp_id)
        self.assertEqual(kwargs["type_"], "POLICY_EXCEPTION_DECIDED")
        self.assertIn("approved", kwargs["title"])
        # NOK, not $ — the whole point of the currency fix.
        self.assertIn("32,000 NOK", kwargs["body"])
        # HR's note is the answer, especially on a rejection.
        self.assertIn("Approved — tight market.", kwargs["body"])
        self.assertEqual(kwargs["metadata"]["status"], "approved")

    def test_resolve_notifies_on_rejection_with_the_reason(self) -> None:
        company = _company_id()
        emp_id = str(uuid.uuid4())
        emp = _make_user(emp_id, "EMPLOYEE", company)
        hr = _make_user(str(uuid.uuid4()), "HR", company)
        created = create_exception_request(
            case_id=str(uuid.uuid4()),
            body=ExceptionRequestCreate(
                category="housing", exception_type="cap_override",
                requested_amount=32000, cap_amount=25000, currency="NOK", reason="r",
            ),
            user=emp,
        )

        with mock.patch.object(
            router_module.db, "create_notification_with_preferences"
        ) as notify:
            resolve_exception_request(
                request_id=created["id"],
                body=ExceptionRequestPatch(status="rejected", hr_note="Outside policy this year."),
                user=hr,
            )

        kwargs = notify.call_args.kwargs
        self.assertIn("declined", kwargs["title"])
        self.assertIn("Outside policy this year.", kwargs["body"])

    def test_resolve_succeeds_when_employee_notification_raises(self) -> None:
        """A broken bell must never cost HR their decision."""
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        hr = _make_user(str(uuid.uuid4()), "HR", company)
        created = create_exception_request(
            case_id=str(uuid.uuid4()),
            body=ExceptionRequestCreate(
                category="housing", exception_type="cap_override",
                requested_amount=1, cap_amount=0, currency="USD", reason="r",
            ),
            user=emp,
        )

        with mock.patch.object(
            router_module.db,
            "create_notification_with_preferences",
            side_effect=RuntimeError("uuid cast failed"),
        ):
            resolved = resolve_exception_request(
                request_id=created["id"],
                body=ExceptionRequestPatch(status="approved"),
                user=hr,
            )

        self.assertEqual(resolved["status"], "approved")

    def test_create_rejects_caller_with_no_company(self) -> None:
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company_id="")
        emp["company"] = None  # no company linked
        body = ExceptionRequestCreate(
            category="housing",
            exception_type="cap_override",
            requested_amount=100,
            cap_amount=50,
            currency="EUR",
            reason="Test",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_exception_request(case_id=str(uuid.uuid4()), body=body, user=emp)
        self.assertEqual(ctx.exception.status_code, 403)

    # ------------------------------------------------------------------
    # GET (list)
    # ------------------------------------------------------------------
    def test_list_scoped_by_organization(self) -> None:
        company_a, company_b = _company_id(), _company_id()
        emp_a = _make_user(str(uuid.uuid4()), "EMPLOYEE", company_a)
        emp_b = _make_user(str(uuid.uuid4()), "EMPLOYEE", company_b)
        case_id = str(uuid.uuid4())
        common_body = lambda: ExceptionRequestCreate(  # noqa: E731
            category="housing",
            exception_type="cap_override",
            requested_amount=1000,
            cap_amount=900,
            currency="EUR",
            reason="r",
        )
        # A creates, B creates on same case_id but different tenant
        create_exception_request(case_id=case_id, body=common_body(), user=emp_a)
        create_exception_request(case_id=case_id, body=common_body(), user=emp_b)

        a_view = list_exception_requests_for_case(case_id=case_id, user=emp_a)
        b_view = list_exception_requests_for_case(case_id=case_id, user=emp_b)
        self.assertEqual(len(a_view), 1)
        self.assertEqual(len(b_view), 1)
        self.assertEqual(a_view[0]["organization_id"], company_a)
        self.assertEqual(b_view[0]["organization_id"], company_b)

    # ------------------------------------------------------------------
    # PATCH
    # ------------------------------------------------------------------
    def test_resolve_by_hr_marks_approved_and_audits(self) -> None:
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        hr = _make_user(str(uuid.uuid4()), "HR", company)
        created = create_exception_request(
            case_id=str(uuid.uuid4()),
            body=ExceptionRequestCreate(
                category="schools",
                exception_type="cap_override",
                requested_amount=20000,
                cap_amount=15000,
                currency="USD",
                reason="International school in Tokyo.",
            ),
            user=emp,
        )

        resolved = resolve_exception_request(
            request_id=created["id"],
            body=ExceptionRequestPatch(status="approved", hr_note="OK for FY26 budget."),
            user=hr,
        )
        self.assertEqual(resolved["status"], "approved")
        self.assertEqual(resolved["hr_note"], "OK for FY26 budget.")
        self.assertEqual(resolved["resolved_by_user_id"], hr["id"])
        self.assertIsNotNone(resolved["resolved_at"])

        rows = self._audit_rows()
        self.assertEqual(len(rows), 2)  # insert + update
        self.assertEqual(rows[1]["action_type"], "update")
        self.assertEqual(rows[1]["actor_id"], hr["id"])

    def test_employee_cannot_resolve(self) -> None:
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        created = create_exception_request(
            case_id=str(uuid.uuid4()),
            body=ExceptionRequestCreate(
                category="movers",
                exception_type="cap_override",
                requested_amount=5000,
                cap_amount=3000,
                currency="EUR",
                reason="Cross-continental move.",
            ),
            user=emp,
        )
        with self.assertRaises(HTTPException) as ctx:
            resolve_exception_request(
                request_id=created["id"],
                body=ExceptionRequestPatch(status="approved"),
                user=emp,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_resolve_blocks_already_resolved(self) -> None:
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        hr = _make_user(str(uuid.uuid4()), "HR", company)
        created = create_exception_request(
            case_id=str(uuid.uuid4()),
            body=ExceptionRequestCreate(
                category="housing",
                exception_type="cap_override",
                requested_amount=100,
                cap_amount=50,
                currency="EUR",
                reason="x",
            ),
            user=emp,
        )
        resolve_exception_request(
            request_id=created["id"],
            body=ExceptionRequestPatch(status="approved"),
            user=hr,
        )
        with self.assertRaises(HTTPException) as ctx:
            resolve_exception_request(
                request_id=created["id"],
                body=ExceptionRequestPatch(status="rejected"),
                user=hr,
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_resolve_other_tenant_returns_404(self) -> None:
        company_a, company_b = _company_id(), _company_id()
        emp_a = _make_user(str(uuid.uuid4()), "EMPLOYEE", company_a)
        hr_b = _make_user(str(uuid.uuid4()), "HR", company_b)
        created = create_exception_request(
            case_id=str(uuid.uuid4()),
            body=ExceptionRequestCreate(
                category="housing",
                exception_type="cap_override",
                requested_amount=100,
                cap_amount=50,
                currency="EUR",
                reason="x",
            ),
            user=emp_a,
        )
        with self.assertRaises(HTTPException) as ctx:
            resolve_exception_request(
                request_id=created["id"],
                body=ExceptionRequestPatch(status="approved"),
                user=hr_b,
            )
        self.assertEqual(ctx.exception.status_code, 404)


    # ------------------------------------------------------------------
    # GET /api/exception-requests (HR queue)
    # ------------------------------------------------------------------
    def test_company_list_hr_only(self) -> None:
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        with self.assertRaises(HTTPException) as ctx:
            list_exception_requests_for_company(status=None, user=emp)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_company_list_filters_by_status(self) -> None:
        company = _company_id()
        emp = _make_user(str(uuid.uuid4()), "EMPLOYEE", company)
        hr = _make_user(str(uuid.uuid4()), "HR", company)
        # 2 created (pending), then resolve one
        a = create_exception_request(case_id=str(uuid.uuid4()), body=ExceptionRequestCreate(
            category="housing", exception_type="cap_override", requested_amount=100, cap_amount=50, currency="EUR", reason="r1",
        ), user=emp)
        create_exception_request(case_id=str(uuid.uuid4()), body=ExceptionRequestCreate(
            category="schools", exception_type="cap_override", requested_amount=200, cap_amount=150, currency="EUR", reason="r2",
        ), user=emp)
        resolve_exception_request(request_id=a["id"],
                                  body=ExceptionRequestPatch(status="approved"),
                                  user=hr)

        all_rows = list_exception_requests_for_company(status=None, user=hr)
        pending = list_exception_requests_for_company(status="pending", user=hr)
        approved = list_exception_requests_for_company(status="approved", user=hr)
        self.assertEqual(len(all_rows), 2)
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]["id"], a["id"])

    def test_company_list_scoped_to_caller_tenant(self) -> None:
        company_a, company_b = _company_id(), _company_id()
        emp_a = _make_user(str(uuid.uuid4()), "EMPLOYEE", company_a)
        emp_b = _make_user(str(uuid.uuid4()), "EMPLOYEE", company_b)
        hr_a = _make_user(str(uuid.uuid4()), "HR", company_a)
        body = lambda: ExceptionRequestCreate(  # noqa: E731
            category="housing", exception_type="cap_override", requested_amount=100, cap_amount=50, currency="EUR", reason="x",
        )
        create_exception_request(case_id=str(uuid.uuid4()), body=body(), user=emp_a)
        create_exception_request(case_id=str(uuid.uuid4()), body=body(), user=emp_b)
        rows = list_exception_requests_for_company(status=None, user=hr_a)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["organization_id"], company_a)


class CallerCompanyResolutionTests(unittest.TestCase):
    """`_caller_company_id` must resolve legacy (non-UUID) ids that have no
    profile.company_id and no `company` token claim — the bug that 403'd the
    demo HR account. Resolution order: profile → token → hr_users → assignment.
    """

    def _call(self, user):
        return router_module._caller_company_id(user)

    def test_profile_company_id_wins(self):
        with mock.patch.object(
            router_module.db, "get_profile_record",
            return_value={"id": "u", "company_id": "comp-profile"},
        ):
            self.assertEqual(self._call({"id": "u"}), "comp-profile")

    def test_token_company_used_when_no_profile(self):
        with mock.patch.object(router_module.db, "get_profile_record", return_value=None):
            self.assertEqual(self._call({"id": "u", "company": "comp-token"}), "comp-token")

    def test_legacy_hr_resolves_via_hr_users(self):
        # No profile.company_id, no token company → hr_users link resolves it.
        with mock.patch.object(router_module.db, "get_profile_record", return_value=None), \
             mock.patch.object(router_module.db, "get_hr_company_id", return_value="comp-hr") as ghc:
            self.assertEqual(self._call({"id": "seed-hr-testingapril"}), "comp-hr")
            ghc.assert_called_once_with("seed-hr-testingapril")

    def test_legacy_employee_resolves_via_assignment(self):
        with mock.patch.object(router_module.db, "get_profile_record", return_value=None), \
             mock.patch.object(router_module.db, "get_hr_company_id", return_value=None), \
             mock.patch.object(
                 router_module.db, "get_assignment_for_employee", return_value={"id": "asg-1"}
             ), \
             mock.patch.object(
                 router_module.db, "get_company_id_for_assignment_id", return_value="comp-asg"
             ):
            self.assertEqual(self._call({"id": "seed-emp-testingapril"}), "comp-asg")

    def test_lookup_failure_degrades_to_403_not_500(self):
        with mock.patch.object(router_module.db, "get_profile_record", return_value=None), \
             mock.patch.object(
                 router_module.db, "get_hr_company_id", side_effect=Exception("no hr_users table")
             ), \
             mock.patch.object(
                 router_module.db, "get_assignment_for_employee", side_effect=Exception("boom")
             ):
            with self.assertRaises(HTTPException) as ctx:
                self._call({"id": "u"})
            self.assertEqual(ctx.exception.status_code, 403)


class ExceptionSelectJoinGuardTests(unittest.TestCase):
    """policy_cap_requests stores id/case_id/*_user_id as TEXT while profiles.id
    and mobility_cases.id are UUID. The shared SELECT projection must cast the
    uuid side to ::text in every join, or `uuid = text` fails to plan and the
    whole endpoint 500s for every caller (regression guard)."""

    def test_joins_cast_uuid_to_text(self) -> None:
        sql = router_module._EXCEPTION_SELECT_WITH_JOINS
        self.assertIn("rp.id::text  = pcr.requested_by_user_id", sql)
        self.assertIn("rsp.id::text = pcr.resolved_by_user_id", sql)
        self.assertIn("mc.id::text  = pcr.case_id", sql)
        # No bare uuid = text comparison left on the joined keys.
        self.assertNotIn("rp.id  = pcr.requested_by_user_id", sql)
        self.assertNotIn("mc.id  = pcr.case_id", sql)

    def test_enrichment_resolves_legacy_ids_and_wizard_corridor(self) -> None:
        """Requester/resolver names fall back to the users.email->profiles.email
        bridge for legacy login ids, and the corridor falls back to wizard_cases
        for wizard/bridged cases (mobility_cases only covers HR-create cases)."""
        sql = router_module._EXCEPTION_SELECT_WITH_JOINS
        self.assertIn("lower(p.email) = lower(u.email)", sql)
        self.assertIn("u.id = pcr.requested_by_user_id", sql)
        self.assertIn("LEFT JOIN wizard_cases   wc  ON wc.id::text  = pcr.case_id", sql)
        # [AIQ-879] corridor also falls back to relocation_cases (home_/host_country)
        # for cases that only materialised there.
        self.assertIn("LEFT JOIN relocation_cases rc2 ON rc2.id::text = pcr.case_id", sql)
        self.assertIn("COALESCE(mc.origin_country, wc.origin_country, rc2.home_country)", sql)
        self.assertIn("COALESCE(mc.destination_country, wc.dest_country, rc2.host_country)", sql)


class HrNotificationHelperTests(unittest.TestCase):
    """[AIQ-1570] `_notify_hr_of_exception_request` — the recipient-resolution and
    skip paths, which decide whether the guardrail actually reaches a human."""

    def _body(self) -> ExceptionRequestCreate:
        return ExceptionRequestCreate(
            category="housing",
            exception_type="cap_override",
            requested_amount=32000,
            cap_amount=25000,
            currency="NOK",
            reason="reason",
        )

    def _notify(self) -> None:
        router_module._notify_hr_of_exception_request(
            request_id="req-1", case_id="case-1", body=self._body()
        )

    def test_no_hr_on_case_skips_quietly(self) -> None:
        with mock.patch.object(
            router_module.db, "get_assignment_by_case_id", return_value={}
        ), mock.patch.object(
            router_module.db, "create_notification_with_preferences"
        ) as notify:
            self._notify()
        notify.assert_not_called()

    def test_legacy_non_uuid_hr_is_skipped_not_faked(self) -> None:
        """notifications.user_id is `uuid NOT NULL` while users.id is `text`. 27 of 239
        prod assignments still carry a legacy hr_user_id (e.g. seed-hr-testingapril);
        the INSERT would fail the uuid cast. Skip + warn — never pretend it was sent."""
        with mock.patch.object(router_module, "_is_sqlite_engine", return_value=False), \
             mock.patch.object(
                 router_module.db,
                 "get_assignment_by_case_id",
                 return_value={"id": "a1", "hr_user_id": "seed-hr-testingapril"},
             ), \
             mock.patch.object(
                 router_module.db, "create_notification_with_preferences"
             ) as notify, \
             self.assertLogs(router_module.logger, level="WARNING") as logs:
            self._notify()

        notify.assert_not_called()
        self.assertIn("HR NOT NOTIFIED", "\n".join(logs.output))

    def test_uuid_hr_is_notified_on_postgres_tier(self) -> None:
        hr_id = str(uuid.uuid4())
        with mock.patch.object(router_module, "_is_sqlite_engine", return_value=False), \
             mock.patch.object(
                 router_module.db,
                 "get_assignment_by_case_id",
                 return_value={"id": "a1", "hr_user_id": hr_id},
             ), \
             mock.patch.object(
                 router_module.db, "create_notification_with_preferences"
             ) as notify:
            self._notify()

        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["user_id"], hr_id)

    def test_legacy_non_uuid_employee_is_skipped_not_faked(self) -> None:
        """Mirror of the HR guard, for the decision half. 244/245 prod employees are
        uuid-castable; the legacy seed-emp-* account cannot receive an in-app notification
        (notifications.user_id is uuid NOT NULL). Skip + warn — never pretend it was sent."""
        row = {
            "requested_by_user_id": "seed-emp-testingapril",
            "category": "housing",
            "currency": "NOK",
            "requested_amount": 32000,
            "case_id": "case-1",
        }
        with mock.patch.object(router_module, "_is_sqlite_engine", return_value=False), \
             mock.patch.object(
                 router_module.db, "create_notification_with_preferences"
             ) as notify, \
             self.assertLogs(router_module.logger, level="WARNING") as logs:
            router_module._notify_employee_of_decision(
                request_id="req-1", existing=row, status="approved", hr_note=None
            )

        notify.assert_not_called()
        self.assertIn("EMPLOYEE NOT NOTIFIED", "\n".join(logs.output))

    def test_decision_notification_without_hr_note_says_so(self) -> None:
        """Silence is not an explanation — say plainly that no note was left rather than
        sending a bare verdict."""
        row = {
            "requested_by_user_id": str(uuid.uuid4()),
            "category": "housing",
            "currency": "NOK",
            "requested_amount": 32000,
            "case_id": "case-1",
        }
        with mock.patch.object(router_module, "_is_sqlite_engine", return_value=False), \
             mock.patch.object(
                 router_module.db, "create_notification_with_preferences"
             ) as notify:
            router_module._notify_employee_of_decision(
                request_id="req-1", existing=row, status="rejected", hr_note=None
            )

        self.assertIn("No note was left", notify.call_args.kwargs["body"])

    def test_notification_failure_is_swallowed(self) -> None:
        with mock.patch.object(
            router_module.db,
            "get_assignment_by_case_id",
            return_value={"id": "a1", "hr_user_id": str(uuid.uuid4())},
        ), mock.patch.object(
            router_module.db,
            "create_notification_with_preferences",
            side_effect=RuntimeError("uuid cast failed"),
        ):
            self._notify()  # must not raise


if __name__ == "__main__":
    unittest.main()
