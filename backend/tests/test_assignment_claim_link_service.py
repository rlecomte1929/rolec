"""Canonical assignment claim/link service (login/signup/employee routes)."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
from backend.database import Database
from backend.services.assignment_claim_link_service import reconcile_pending_assignment_claims
from backend.services.unified_assignment_creation import create_assignment_with_contact_and_invites


def _seed_company(db: Database, company_id: str, name: str = "Test Co") -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": name, "ca": now},
        )


class AssignmentClaimLinkServiceTests(unittest.TestCase):
    def setUp(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self._prev_engine = dbmod._engine
        self._prev_sqlite = dbmod._is_sqlite
        dbmod._engine = eng
        dbmod._is_sqlite = True
        self.db = Database()

    def tearDown(self):
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def test_existing_account_pending_assignment_via_email(self):
        """Simulates post-login reconcile: user exists, assignment waiting on contact."""
        db = self.db
        _seed_company(db, "co-cl-1")
        hr = "hr-cl-1"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-cl-1")
        email = "existing.pending@claim.example"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-cl-1",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        uid = str(uuid.uuid4())
        self.assertTrue(db.create_user(uid, None, email, "h", "EMPLOYEE", "E"))

        res = reconcile_pending_assignment_claims(
            db,
            user_id=uid,
            email=email,
            username=None,
            role="EMPLOYEE",
            request_id=None,
            emit_side_effects=False,
        )
        self.assertIn(r.assignment_id, res.newly_attached_assignment_ids)
        self.assertEqual(db.get_assignment_by_id(r.assignment_id).get("employee_user_id"), uid)

    def test_new_account_same_as_reconcile_after_create_user(self):
        db = self.db
        _seed_company(db, "co-cl-2")
        hr = "hr-cl-2"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-cl-2")
        email = "new.user@claim.example"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-cl-2",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        uid = str(uuid.uuid4())
        self.assertTrue(db.create_user(uid, None, email, "h", "EMPLOYEE", "N"))
        res = reconcile_pending_assignment_claims(
            db,
            user_id=uid,
            email=email,
            username=None,
            role="EMPLOYEE",
            emit_side_effects=False,
        )
        self.assertEqual(len(res.newly_attached_assignment_ids), 1)
        self.assertEqual(res.newly_attached_assignment_ids[0], r.assignment_id)

    def test_repeated_reconcile_idempotent(self):
        db = self.db
        _seed_company(db, "co-cl-3")
        hr = "hr-cl-3"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-cl-3")
        email = "idempotent@claim.example"
        create_assignment_with_contact_and_invites(
            db,
            company_id="co-cl-3",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        uid = str(uuid.uuid4())
        self.assertTrue(db.create_user(uid, None, email, "h", "EMPLOYEE", "I"))
        r1 = reconcile_pending_assignment_claims(
            db, user_id=uid, email=email, username=None, role="EMPLOYEE", emit_side_effects=False
        )
        self.assertEqual(len(r1.newly_attached_assignment_ids), 1)
        r2 = reconcile_pending_assignment_claims(
            db, user_id=uid, email=email, username=None, role="EMPLOYEE", emit_side_effects=False
        )
        self.assertEqual(r2.newly_attached_assignment_ids, [])
        self.assertEqual(db.get_assignment_by_id(r1.newly_attached_assignment_ids[0]).get("employee_user_id"), uid)

    def test_assignment_owned_by_other_user_skipped_when_row_stale(self):
        """If an assignment row still shows unassigned but DB has another owner, re-fetch avoids stealing."""
        db = self.db
        _seed_company(db, "co-cl-4")
        hr = "hr-cl-4"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-cl-4")
        email = "already@claim.example"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-cl-4",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        owner = str(uuid.uuid4())
        intruder = str(uuid.uuid4())
        self.assertTrue(db.create_user(owner, None, email, "h", "EMPLOYEE", "O"))
        self.assertTrue(db.create_user(intruder, None, "intruder@x.com", "h", "EMPLOYEE", "X"))
        db.attach_employee_to_assignment(r.assignment_id, owner, request_id=None)
        stale = dict(db.get_assignment_by_id(r.assignment_id) or {})
        stale["employee_user_id"] = None
        from backend.services.assignment_claim_link_service import ClaimLinkResult, _try_attach_assignment

        res = ClaimLinkResult()
        _try_attach_assignment(
            db,
            user_id=intruder,
            assignment=stale,
            mark_identifier=email,
            request_id=None,
            emit_side_effects=False,
            result=res,
        )
        self.assertGreaterEqual(res.skipped_assignments_linked_to_other_user, 1)
        self.assertEqual(db.get_assignment_by_id(r.assignment_id).get("employee_user_id"), owner)

    def test_revoked_claim_invite_blocks_auto_attach(self):
        db = self.db
        _seed_company(db, "co-cl-5")
        hr = "hr-cl-5"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-cl-5")
        email = "revoked@claim.example"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-cl-5",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        ecid = r.employee_contact_id
        self.assertTrue(ecid)
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE assignment_claim_invites SET status = 'revoked' "
                    "WHERE assignment_id = :aid"
                ),
                {"aid": r.assignment_id},
            )
        uid = str(uuid.uuid4())
        self.assertTrue(db.create_user(uid, None, email, "h", "EMPLOYEE", "R"))
        res = reconcile_pending_assignment_claims(
            db, user_id=uid, email=email, username=None, role="EMPLOYEE", emit_side_effects=False
        )
        self.assertEqual(res.newly_attached_assignment_ids, [])
        self.assertGreaterEqual(res.skipped_revoked_invites, 1)
        self.assertIsNone(db.get_assignment_by_id(r.assignment_id).get("employee_user_id"))

    def test_username_principal_matches_invite_key(self):
        db = self.db
        _seed_company(db, "co-cl-6")
        hr = "hr-cl-6"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-cl-6")
        uname = "janedoe_claim"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-cl-6",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=uname,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        uid = str(uuid.uuid4())
        self.assertTrue(db.create_user(uid, uname, None, "h", "EMPLOYEE", "Jane"))
        res = reconcile_pending_assignment_claims(
            db,
            user_id=uid,
            email=None,
            username=uname,
            role="EMPLOYEE",
            emit_side_effects=False,
        )
        self.assertIn(r.assignment_id, res.newly_attached_assignment_ids)


if __name__ == "__main__":
    unittest.main()
