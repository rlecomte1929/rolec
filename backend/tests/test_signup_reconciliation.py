"""Signup reconciliation: link new auth user to pre-provisioned contacts/assignments."""
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
from backend.services.signup_reconciliation import reconcile_employee_signup_after_register
from backend.services.unified_assignment_creation import create_assignment_with_contact_and_invites


def _seed_company(db: Database, company_id: str, name: str = "Test Co") -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": name, "ca": now},
        )


class SignupReconciliationTests(unittest.TestCase):
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

    def test_reconcile_links_hr_created_assignment(self):
        """After signup, unclaimed assignment created via unified path is attached to the new user."""
        db = self.db
        _seed_company(db, "co-sign-1")
        hr = "hr-sign-1"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-sign-1")
        email = "pending.employee@sign.example"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-sign-1",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name="Pat",
            employee_last_name="Pending",
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        self.assertIsNone(r.employee_user_id)
        self.assertTrue(r.employee_contact_id)

        new_uid = str(uuid.uuid4())
        created = db.create_user(
            new_uid,
            None,
            email,
            "hash",
            "EMPLOYEE",
            "Pat Pending",
        )
        self.assertTrue(created)

        rec = reconcile_employee_signup_after_register(
            db, user_id=new_uid, email=email, role="EMPLOYEE", request_id=None
        )
        self.assertEqual(rec["attachedAssignmentIds"], [])
        self.assertIn(r.employee_contact_id, rec["linkedContactIds"])

        asn = db.get_assignment_by_id(r.assignment_id)
        self.assertIsNone(asn.get("employee_user_id"))

        ec = db.get_employee_contact_by_id(r.employee_contact_id)
        self.assertEqual(ec.get("linked_auth_user_id"), new_uid)
        db.attach_employee_to_assignment(r.assignment_id, new_uid, request_id=None)
        self.assertEqual(db.get_assignment_by_id(r.assignment_id).get("employee_user_id"), new_uid)

    def test_reconcile_admin_created_same_as_hr_path(self):
        """Admin-style assignment (same unified creation) reconciles the same way."""
        db = self.db
        _seed_company(db, "co-sign-2")
        hr = "hr-sign-2"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-sign-2")
        email = "admin.provisioned@sign.example"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-sign-2",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        new_uid = str(uuid.uuid4())
        self.assertTrue(
            db.create_user(new_uid, None, email, "hash", "EMPLOYEE", "A")
        )
        rec = reconcile_employee_signup_after_register(
            db, user_id=new_uid, email=email, role="EMPLOYEE", request_id=None
        )
        self.assertEqual(rec["attachedAssignmentIds"], [])
        db.attach_employee_to_assignment(r.assignment_id, new_uid, request_id=None)
        self.assertEqual(db.get_assignment_by_id(r.assignment_id).get("employee_user_id"), new_uid)

    def test_reconcile_no_pending_records(self):
        db = self.db
        new_uid = str(uuid.uuid4())
        self.assertTrue(
            db.create_user(new_uid, None, "solo@sign.example", "hash", "EMPLOYEE", "Solo")
        )
        rec = reconcile_employee_signup_after_register(
            db, user_id=new_uid, email="solo@sign.example", role="EMPLOYEE", request_id=None
        )
        self.assertEqual(rec["linkedContactIds"], [])
        self.assertEqual(rec["attachedAssignmentIds"], [])
        self.assertIsNone(rec.get("message"))

    def test_reconcile_skips_contact_linked_to_another_auth_user(self):
        db = self.db
        _seed_company(db, "co-sign-3")
        hr = "hr-sign-3"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-sign-3")
        email = "disputed@sign.example"
        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-sign-3",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw=email,
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        other = str(uuid.uuid4())
        self.assertTrue(
            db.create_user(other, None, "other@sign.example", "h", "EMPLOYEE", "O")
        )
        db.link_employee_contact_to_auth_user(r.employee_contact_id, other, request_id=None)

        new_uid = str(uuid.uuid4())
        self.assertTrue(
            db.create_user(new_uid, None, email, "hash", "EMPLOYEE", "N")
        )
        rec = reconcile_employee_signup_after_register(
            db, user_id=new_uid, email=email, role="EMPLOYEE", request_id=None
        )
        self.assertEqual(rec["skippedContactsLinkedToOtherUser"], 1)
        self.assertEqual(rec["attachedAssignmentIds"], [])
        asn = db.get_assignment_by_id(r.assignment_id)
        self.assertIsNone(asn.get("employee_user_id"))

    def test_second_signup_blocked_only_by_users_table(self):
        """Only public.users email uniqueness prevents registration — not employee_contacts."""
        db = self.db
        email = "already.auth@sign.example"
        u1 = str(uuid.uuid4())
        self.assertTrue(db.create_user(u1, None, email, "h", "EMPLOYEE", "First"))
        u2 = str(uuid.uuid4())
        ok = db.create_user(u2, None, email, "h2", "EMPLOYEE", "Second")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
