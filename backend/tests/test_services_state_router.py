"""
Tests for backend/app/routers/services_state.py.

Same direct-call pattern as test_exception_requests_router.py — bypasses the
FastAPI app wiring so the broader main.py import issues don't bleed in.
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


def _user(role: str, company: str):
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

    def test_get_404_when_no_state_for_case(self) -> None:
        emp = _user("EMPLOYEE", str(uuid.uuid4()))
        with self.assertRaises(HTTPException) as ctx:
            get_services_state(case_id=str(uuid.uuid4()), user=emp)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_put_then_get_round_trip(self) -> None:
        emp = _user("EMPLOYEE", str(uuid.uuid4()))
        case_id = str(uuid.uuid4())
        body = ServicesStatePut(state={
            "selectedServices": ["housing", "movers"],
            "answers": {"budget_min": 2000, "budget_max": 5000},
            "shortlist": [["housing", "rec_a"], ["movers", "rec_b"]],
            "displayCurrency": "EUR",
        })
        saved = put_services_state(case_id=case_id, body=body, user=emp)
        self.assertEqual(saved["case_id"], case_id)
        self.assertEqual(saved["state"]["displayCurrency"], "EUR")

        fetched = get_services_state(case_id=case_id, user=emp)
        self.assertEqual(fetched["state"]["selectedServices"], ["housing", "movers"])
        self.assertEqual(fetched["state"]["answers"]["budget_max"], 5000)

    def test_put_inserts_then_updates_in_place(self) -> None:
        emp = _user("EMPLOYEE", str(uuid.uuid4()))
        case_id = str(uuid.uuid4())
        put_services_state(
            case_id=case_id,
            body=ServicesStatePut(state={"v": 1}),
            user=emp,
        )
        put_services_state(
            case_id=case_id,
            body=ServicesStatePut(state={"v": 2}),
            user=emp,
        )
        with self.engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM services_state WHERE case_id = :id"),
                {"id": case_id},
            ).scalar()
        self.assertEqual(count, 1)
        latest = get_services_state(case_id=case_id, user=emp)
        self.assertEqual(latest["state"]["v"], 2)

    def test_get_scoped_by_organization(self) -> None:
        emp_a = _user("EMPLOYEE", str(uuid.uuid4()))
        hr_b = _user("HR", str(uuid.uuid4()))
        case_id = str(uuid.uuid4())
        put_services_state(
            case_id=case_id,
            body=ServicesStatePut(state={"v": "a"}),
            user=emp_a,
        )
        # HR from a different org cannot read it.
        with self.assertRaises(HTTPException) as ctx:
            get_services_state(case_id=case_id, user=hr_b)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_put_other_tenant_case_id_returns_404(self) -> None:
        emp_a = _user("EMPLOYEE", str(uuid.uuid4()))
        emp_b = _user("EMPLOYEE", str(uuid.uuid4()))
        case_id = str(uuid.uuid4())
        put_services_state(
            case_id=case_id,
            body=ServicesStatePut(state={"v": "a"}),
            user=emp_a,
        )
        with self.assertRaises(HTTPException) as ctx:
            put_services_state(
                case_id=case_id,
                body=ServicesStatePut(state={"v": "b-overwrite"}),
                user=emp_b,
            )
        self.assertEqual(ctx.exception.status_code, 404)
        # Original tenant's data unchanged.
        kept = get_services_state(case_id=case_id, user=emp_a)
        self.assertEqual(kept["state"]["v"], "a")

    def test_put_audit_row_written(self) -> None:
        emp = _user("EMPLOYEE", str(uuid.uuid4()))
        case_id = str(uuid.uuid4())
        put_services_state(
            case_id=case_id,
            body=ServicesStatePut(state={"hello": "world"}),
            user=emp,
        )
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["entity_type"], "services_state")
        self.assertEqual(rows[0]["entity_id"], case_id)
        self.assertEqual(rows[0]["action_type"], "insert")
        self.assertEqual(rows[0]["actor_id"], emp["id"])

    def test_put_rejects_oversize_payload(self) -> None:
        emp = _user("EMPLOYEE", str(uuid.uuid4()))
        case_id = str(uuid.uuid4())
        # Build a state larger than MAX_STATE_BYTES once serialized.
        oversized = {"big": "x" * (MAX_STATE_BYTES + 100)}
        with self.assertRaises(HTTPException) as ctx:
            put_services_state(
                case_id=case_id,
                body=ServicesStatePut(state=oversized),
                user=emp,
            )
        self.assertEqual(ctx.exception.status_code, 413)

    def test_put_rejects_caller_with_no_company(self) -> None:
        emp = _user("EMPLOYEE", "")
        emp["company"] = None
        with self.assertRaises(HTTPException) as ctx:
            put_services_state(
                case_id=str(uuid.uuid4()),
                body=ServicesStatePut(state={}),
                user=emp,
            )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
