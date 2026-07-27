"""
Tests for backend/app/routers/services_state.py.

Same direct-call pattern as test_exception_requests_router.py — bypasses the
FastAPI app wiring so the broader main.py import issues don't bleed in.

[AIQ-1012] The router authorizes the case via require_case_access, then derives
the tenant from the CASE record (relocation_cases.company_id) rather than the
caller's profile. These tests mock require_case_access (case ownership) and
db.get_case_by_id (the case's tenant) accordingly.
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

from backend.app.routers import services_state as router_module  # noqa: E402
from backend.app.routers.services_state import (  # noqa: E402
    MAX_STATE_BYTES,
    ServicesStatePut,
    _parse_state_json,
    get_services_state,
    put_services_state,
)
from fastapi import HTTPException  # noqa: E402


SCHEMA = """
CREATE TABLE services_state (
  case_id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  state_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by_user_id TEXT
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
"""


def _user(role: str = "EMPLOYEE", company=None):
    # company is intentionally optional/None — the tenant comes from the case
    # now, not the caller (AIQ-1012). Production-shaped employees have no
    # profiles.company_id.
    return {
        "id": str(uuid.uuid4()),
        "role": role,
        "company": company,
        "is_admin": False,
    }


class ServicesStateRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

        # _jbind() wraps JSON params in CAST(:p AS jsonb) on postgres. sqlite has
        # no jsonb cast, so pin it to emit a bare ":p" for these tests (the real
        # helper does this on sqlite anyway; pinning keeps the test hermetic
        # regardless of the ambient DATABASE_URL).
        self.jb_patcher = mock.patch.object(
            router_module, "_jbind", lambda name: f":{name}"
        )
        self.jb_patcher.start()
        self.addCleanup(self.jb_patcher.stop)

        # Tenant comes from the case record. Map case_id -> company_id; an
        # unknown case defaults to a single shared org so most tests are
        # one-tenant.
        self._default_org = str(uuid.uuid4())
        self.case_org: dict = {}
        # case_ids that require_case_access must DENY (cross-tenant / not owner).
        self.denied_cases: set = set()

        def _fake_require_case_access(case_id, user):
            if case_id in self.denied_cases:
                raise HTTPException(status_code=403, detail="Not authorized for this assignment")
            return {
                "id": f"asg-{case_id}",
                "hr_user_id": "hr-" + str(user["id"])[:8],
                "employee_user_id": user["id"],
            }

        self.rca_patcher = mock.patch.object(
            router_module, "require_case_access", side_effect=_fake_require_case_access
        )
        self.rca_patcher.start()
        self.addCleanup(self.rca_patcher.stop)

        def _fake_get_case_by_id(case_id):
            org = self.case_org.get(case_id, self._default_org)
            return {"id": case_id, "company_id": org}

        self.case_patcher = mock.patch.object(
            router_module.db, "get_case_by_id", side_effect=_fake_get_case_by_id
        )
        self.case_patcher.start()
        self.addCleanup(self.case_patcher.stop)

        # [AIQ-1717] The router now resolves the route id to the canonical case id
        # before any query (_canonical_services_case_id). `db` is a MagicMock under
        # backend/conftest.py, so an unpatched db.resolve_case_ids returns a truthy
        # Mock whose .canonical_case_id is itself a Mock — which sqlite then refuses
        # to bind. Return None here: these tests already address cases by their
        # canonical id, which is exactly the no-assignment passthrough branch.
        # The resolve branch is covered by test_services_state_canonical_id.py.
        self.resolve_patcher = mock.patch.object(
            router_module.db, "resolve_case_ids", return_value=None
        )
        self.resolve_patcher.start()
        self.addCleanup(self.resolve_patcher.stop)

        # HR-company fallback only fires when the case row has no company_id.
        self.hr_patcher = mock.patch.object(
            router_module.db, "get_hr_company_id", side_effect=lambda hid: None
        )
        self.hr_patcher.start()
        self.addCleanup(self.hr_patcher.stop)

        # Production-shaped: caller profile has no company_id. The fix must not
        # depend on this anymore.
        self.profile_patcher = mock.patch.object(
            router_module.db,
            "get_profile_record",
            side_effect=lambda uid: {"id": uid, "company_id": None},
        )
        self.profile_patcher.start()
        self.addCleanup(self.profile_patcher.stop)

    def _audit_rows(self):
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text(
                        "SELECT entity_type, entity_id, action_type, actor_id "
                        "FROM audit_logs ORDER BY rowid"
                    )
                ).mappings()
            )

    def test_get_returns_empty_state_when_none_saved(self) -> None:
        # AIQ-1320: an authorized case with no saved state yet returns 200 + an
        # empty state (not 404), so the browser doesn't log a console error on
        # the first services visit. Access is still enforced above (see
        # test_case_access_denied_blocks_read).
        case_id = str(uuid.uuid4())
        result = get_services_state(case_id=case_id, user=_user())
        self.assertEqual(result["state"], {})
        self.assertEqual(result["case_id"], case_id)
        self.assertEqual(result["updated_at"], "")

    def test_put_then_get_round_trip(self) -> None:
        emp = _user()
        case_id = str(uuid.uuid4())
        body = ServicesStatePut(state={
            "selectedServices": ["housing", "movers"],
            "answers": {"budget_min": 2000, "budget_max": 5000},
            "shortlist": [["housing", "rec_a"], ["movers", "rec_b"]],
            "displayCurrency": "EUR",
        })
        saved = put_services_state(case_id=case_id, body=body, user=emp)
        self.assertEqual(saved["case_id"], case_id)
        self.assertEqual(saved["organization_id"], self._default_org)
        self.assertEqual(saved["state"]["displayCurrency"], "EUR")

        fetched = get_services_state(case_id=case_id, user=emp)
        self.assertEqual(fetched["state"]["selectedServices"], ["housing", "movers"])
        self.assertEqual(fetched["state"]["answers"]["budget_max"], 5000)

    def test_production_shaped_employee_no_profile_company_succeeds(self) -> None:
        """Regression for AIQ-1012: an employee whose profile has no company_id
        (company is via the assignment) can still GET/PUT — the tenant comes from
        the case, not the caller. Previously this 403'd before case access was
        even checked."""
        emp = _user(company=None)  # no caller company anywhere
        case_id = str(uuid.uuid4())
        case_org = str(uuid.uuid4())
        self.case_org[case_id] = case_org
        saved = put_services_state(
            case_id=case_id, body=ServicesStatePut(state={"ok": True}), user=emp
        )
        self.assertEqual(saved["organization_id"], case_org)
        fetched = get_services_state(case_id=case_id, user=emp)
        self.assertEqual(fetched["state"]["ok"], True)
        self.assertEqual(fetched["organization_id"], case_org)

    def test_put_inserts_then_updates_in_place(self) -> None:
        emp = _user()
        case_id = str(uuid.uuid4())
        put_services_state(case_id=case_id, body=ServicesStatePut(state={"v": 1}), user=emp)
        put_services_state(case_id=case_id, body=ServicesStatePut(state={"v": 2}), user=emp)
        with self.engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM services_state WHERE case_id = :id"),
                {"id": case_id},
            ).scalar()
        self.assertEqual(count, 1)
        latest = get_services_state(case_id=case_id, user=emp)
        self.assertEqual(latest["state"]["v"], 2)

    def test_case_access_denied_blocks_read(self) -> None:
        """Cross-tenant / non-owner access is rejected by require_case_access
        before any tenant derivation — the caller can't reach the data."""
        emp_a = _user()
        case_id = str(uuid.uuid4())
        put_services_state(case_id=case_id, body=ServicesStatePut(state={"v": "a"}), user=emp_a)
        # A user the case-access check denies cannot read it.
        self.denied_cases.add(case_id)
        with self.assertRaises(HTTPException) as ctx:
            get_services_state(case_id=case_id, user=_user("HR"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_put_existing_row_org_mismatch_returns_404(self) -> None:
        """Defense-in-depth: if a services_state row exists under a different
        org than the case now resolves to, the overwrite is refused as 404."""
        emp = _user()
        case_id = str(uuid.uuid4())
        self.case_org[case_id] = str(uuid.uuid4())
        put_services_state(case_id=case_id, body=ServicesStatePut(state={"v": "a"}), user=emp)
        # The case now resolves to a different tenant than the stored row.
        self.case_org[case_id] = str(uuid.uuid4())
        with self.assertRaises(HTTPException) as ctx:
            put_services_state(
                case_id=case_id, body=ServicesStatePut(state={"v": "b"}), user=emp
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_case_with_no_tenant_returns_403(self) -> None:
        """If the case record has no company_id and the HR fallback yields
        nothing, _org_id_for_case raises 403."""
        emp = _user()
        case_id = str(uuid.uuid4())
        with mock.patch.object(
            router_module.db,
            "get_case_by_id",
            side_effect=lambda cid: {"id": cid, "company_id": None},
        ):
            # hr_patcher already returns None for the fallback.
            with self.assertRaises(HTTPException) as ctx:
                put_services_state(
                    case_id=case_id, body=ServicesStatePut(state={"v": 1}), user=emp
                )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_put_falls_back_to_hr_company_when_case_has_no_company(self) -> None:
        """When relocation_cases.company_id is null, the tenant falls back to the
        assignment's HR user's company."""
        emp = _user()
        case_id = str(uuid.uuid4())
        hr_org = str(uuid.uuid4())
        with mock.patch.object(
            router_module.db,
            "get_case_by_id",
            side_effect=lambda cid: {"id": cid, "company_id": None},
        ), mock.patch.object(
            router_module.db, "get_hr_company_id", side_effect=lambda hid: hr_org
        ):
            saved = put_services_state(
                case_id=case_id, body=ServicesStatePut(state={"v": 1}), user=emp
            )
        self.assertEqual(saved["organization_id"], hr_org)

    def test_put_audit_row_written(self) -> None:
        emp = _user()
        case_id = str(uuid.uuid4())
        put_services_state(
            case_id=case_id, body=ServicesStatePut(state={"hello": "world"}), user=emp
        )
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["entity_type"], "services_state")
        self.assertEqual(rows[0]["entity_id"], case_id)
        self.assertEqual(rows[0]["action_type"], "insert")
        self.assertEqual(rows[0]["actor_id"], emp["id"])

    def test_put_rejects_oversize_payload(self) -> None:
        emp = _user()
        case_id = str(uuid.uuid4())
        oversized = {"big": "x" * (MAX_STATE_BYTES + 100)}
        with self.assertRaises(HTTPException) as ctx:
            put_services_state(
                case_id=case_id, body=ServicesStatePut(state=oversized), user=emp
            )
        self.assertEqual(ctx.exception.status_code, 413)


class ParseStateJsonTests(unittest.TestCase):
    """AIQ-1320: state_json is JSONB — psycopg2 returns it as a dict on Postgres,
    while SQLite returns TEXT. The GET must handle both (the old json.loads() 404'd
    every Postgres read once a row existed)."""

    def test_dict_from_jsonb_postgres(self):
        self.assertEqual(_parse_state_json({"selectedServices": ["banks"]}),
                         {"selectedServices": ["banks"]})

    def test_list_from_jsonb(self):
        self.assertEqual(_parse_state_json([1, 2]), [1, 2])

    def test_text_from_sqlite(self):
        self.assertEqual(_parse_state_json('{"a": 1}'), {"a": 1})

    def test_none_and_empty(self):
        self.assertEqual(_parse_state_json(None), {})
        self.assertEqual(_parse_state_json(""), {})

    def test_corrupt_text_raises(self):
        with self.assertRaises(ValueError):
            _parse_state_json("{not json")


if __name__ == "__main__":
    unittest.main()
