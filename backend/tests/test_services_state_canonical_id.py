"""AIQ-1704 follow-up: services-state must persist under the CANONICAL case id.

put_services_state authorizes a 3-form id via require_case_access, then keys the
services_state row on case_id. It used to bind the RAW path id — so a POST carrying
an assignment id wrote a row keyed on the assignment id, which the read path (keyed
on the case id) could never find. services_state.case_id is UNIQUE, so a case could
hold only one of the two keys → dropped / phantom state (the review-validator's
worst-case for the AIQ-1704 guard). The fix derives the canonical case id from the
assignment require_case_access returns before touching the table.

Direct-call harness (mirrors test_services_state_router.py) with an assignment whose
canonical_case_id DIFFERS from the id the caller passed.
"""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, text  # noqa: E402

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import services_state as router_module  # noqa: E402
from backend.app.routers.services_state import (  # noqa: E402
    ServicesStatePut,
    get_services_state,
    put_services_state,
)

SCHEMA = """
CREATE TABLE services_state (
  case_id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  state_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by_user_id TEXT
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL, old_value_json TEXT, new_value_json TEXT,
  actor_type TEXT NOT NULL, actor_id TEXT, created_at TEXT
);
"""

_ASSIGNMENT_ID = "asg-9"
_CANONICAL_CASE_ID = "canon-9"  # what services_state rows must be keyed on
_ORG = str(uuid.uuid4())


class ServicesStateCanonicalIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        for target, attr, val in [
            (router_module.db, "engine", self.engine),
            (router_module, "_jbind", lambda name: f":{name}"),
        ]:
            p = mock.patch.object(target, attr, val); p.start(); self.addCleanup(p.stop)

        # The caller passes the ASSIGNMENT id; require_case_access authorizes it and
        # returns the assignment carrying the canonical case id (!= the passed id).
        def _rca(case_id, user):
            return {"id": _ASSIGNMENT_ID, "canonical_case_id": _CANONICAL_CASE_ID,
                    "case_id": _CANONICAL_CASE_ID, "hr_user_id": "hr-1",
                    "employee_user_id": user["id"]}
        for attr, side in [
            ("require_case_access", _rca),
        ]:
            p = mock.patch.object(router_module, attr, side_effect=side); p.start(); self.addCleanup(p.stop)
        for attr, side in [
            ("get_case_by_id", lambda cid: {"id": cid, "company_id": _ORG}),
            ("get_hr_company_id", lambda hid: None),
            ("get_profile_record", lambda uid: {"id": uid, "company_id": None}),
        ]:
            p = mock.patch.object(router_module.db, attr, side_effect=side); p.start(); self.addCleanup(p.stop)

    def _user(self):
        return {"id": str(uuid.uuid4()), "role": "EMPLOYEE", "company": None, "is_admin": False}

    def _stored_case_ids(self):
        with self.engine.connect() as conn:
            return [r[0] for r in conn.execute(text("SELECT case_id FROM services_state")).all()]

    def test_post_with_assignment_id_persists_under_canonical(self):
        put_services_state(
            case_id=_ASSIGNMENT_ID,
            body=ServicesStatePut(state={"selectedServices": ["movers"]}),
            user=self._user(),
        )
        # THE FIX: the row is keyed on the canonical case id, NOT the assignment id.
        self.assertEqual(self._stored_case_ids(), [_CANONICAL_CASE_ID])

    def test_get_with_assignment_id_reads_the_canonical_row(self):
        put_services_state(
            case_id=_ASSIGNMENT_ID,
            body=ServicesStatePut(state={"selectedServices": ["movers", "banking"]}),
            user=self._user(),
        )
        # A GET with the SAME assignment id resolves to the canonical row (not empty).
        result = get_services_state(case_id=_ASSIGNMENT_ID, user=self._user())
        self.assertEqual(result["case_id"], _CANONICAL_CASE_ID)
        self.assertEqual(result["state"], {"selectedServices": ["movers", "banking"]})

    def test_no_phantom_second_row(self):
        # POST twice with the assignment id → exactly ONE canonical row (UNIQUE holds).
        for _ in range(2):
            put_services_state(
                case_id=_ASSIGNMENT_ID,
                body=ServicesStatePut(state={"selectedServices": ["movers"]}),
                user=self._user(),
            )
        self.assertEqual(self._stored_case_ids(), [_CANONICAL_CASE_ID])


if __name__ == "__main__":
    unittest.main()
