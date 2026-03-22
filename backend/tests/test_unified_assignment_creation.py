"""Tests for canonical HR/Admin assignment creation service (stdlib unittest)."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
from backend.database import Database
from backend.services.unified_assignment_creation import create_assignment_with_contact_and_invites


def _seed_company(db: Database, company_id: str, name: str = "Test Co") -> None:
    """Minimal company row (avoids create_company() which uses Postgres information_schema)."""
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": name, "ca": now},
        )


def _count_employee_contacts(db: Database, company_id: str) -> int:
    with db.engine.connect() as conn:
        row = conn.execute(
            text("SELECT COUNT(*) AS n FROM employee_contacts WHERE company_id = :c"),
            {"c": company_id},
        ).fetchone()
    return int(row[0] if row and row[0] is not None else 0)


class UnifiedAssignmentCreationTests(unittest.TestCase):
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

    def test_first_assignment_creates_contact_and_pending_invite(self):
        db = self.db
        _seed_company(db, "co-uni-1", "Uni Co")
        hr = "hr-uni-1"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-uni-1")

        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-uni-1",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw="first.assignee@unico.example",
            employee_first_name="First",
            employee_last_name="Assignee",
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )

        self.assertTrue(r.employee_contact_id)
        self.assertTrue(r.invite_token)
        self.assertEqual(r.stored_identifier, "first.assignee@unico.example")
        self.assertEqual(_count_employee_contacts(db, "co-uni-1"), 1)

        asn = db.get_assignment_by_id(r.assignment_id)
        self.assertIsNotNone(asn)
        self.assertEqual(asn.get("employee_contact_id"), r.employee_contact_id)
        self.assertEqual((asn.get("employee_link_mode") or "").lower(), "pending_claim")

    def test_second_assignment_reuses_same_contact_same_company(self):
        db = self.db
        _seed_company(db, "co-uni-2", "Uni Co 2")
        hr = "hr-uni-2"
        case1, case2 = str(uuid.uuid4()), str(uuid.uuid4())
        db.create_case(case1, hr, {}, company_id="co-uni-2")
        db.create_case(case2, hr, {}, company_id="co-uni-2")

        r1 = create_assignment_with_contact_and_invites(
            db,
            company_id="co-uni-2",
            hr_user_id=hr,
            case_id=case1,
            employee_identifier_raw="reuse.me@unico.example",
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )
        r2 = create_assignment_with_contact_and_invites(
            db,
            company_id="co-uni-2",
            hr_user_id=hr,
            case_id=case2,
            employee_identifier_raw="  ReUse.ME@unico.example ",
            employee_first_name=None,
            employee_last_name=None,
            employee_user_id=None,
            assignment_status="assigned",
            request_id=None,
        )

        self.assertEqual(r1.employee_contact_id, r2.employee_contact_id)
        self.assertEqual(_count_employee_contacts(db, "co-uni-2"), 1)
        self.assertNotEqual(r1.assignment_id, r2.assignment_id)
        self.assertTrue(r1.invite_token and r2.invite_token)
        self.assertNotEqual(r1.invite_token, r2.invite_token)

        with db.engine.connect() as conn:
            n_pending = conn.execute(
                text("SELECT COUNT(*) FROM assignment_claim_invites WHERE status = 'pending'")
            ).scalar()
        self.assertEqual(int(n_pending or 0), 2)

    def test_assignment_for_existing_linked_auth_user_skips_invites(self):
        db = self.db
        _seed_company(db, "co-uni-3", "Uni Co 3")
        hr = "hr-uni-3"
        uid = "profile-linked-uni-3"
        db.create_user(
            uid,
            None,
            "already.signed@unico.example",
            "dummy-hash",
            "EMPLOYEE",
            "Signed User",
        )
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-uni-3")

        r = create_assignment_with_contact_and_invites(
            db,
            company_id="co-uni-3",
            hr_user_id=hr,
            case_id=case_id,
            employee_identifier_raw="already.signed@unico.example",
            employee_first_name="Already",
            employee_last_name="Signed",
            employee_user_id=uid,
            assignment_status="assigned",
            request_id=None,
        )

        self.assertTrue(r.employee_contact_id)
        self.assertEqual(r.employee_user_id, uid)
        self.assertIsNone(r.invite_token)

        ec = db.get_employee_contact_by_id(r.employee_contact_id)
        self.assertIsNotNone(ec)
        self.assertEqual(ec.get("linked_auth_user_id"), uid)

        with db.engine.connect() as conn:
            n_claim = conn.execute(
                text("SELECT COUNT(*) FROM assignment_claim_invites WHERE assignment_id = :aid"),
                {"aid": r.assignment_id},
            ).scalar()
        self.assertEqual(int(n_claim or 0), 0)

    def test_ensure_pending_invite_reuses_existing_row(self):
        db = self.db
        _seed_company(db, "co-uni-4", "Uni Co 4")
        hr = "hr-uni-4"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-uni-4")
        aid = str(uuid.uuid4())
        ecid = db.resolve_or_create_employee_contact(
            "co-uni-4",
            "idempotent@unico.example",
            first_name=None,
            last_name=None,
            request_id=None,
        )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier="idempotent@unico.example",
            status="assigned",
            employee_contact_id=ecid,
        )
        t1 = db.ensure_pending_assignment_invites(
            aid,
            case_id,
            hr,
            ecid,
            "idempotent@unico.example",
            "idempotent@unico.example",
            request_id=None,
        )
        t2 = db.ensure_pending_assignment_invites(
            aid,
            case_id,
            hr,
            ecid,
            "idempotent@unico.example",
            "idempotent@unico.example",
            request_id=None,
        )
        self.assertEqual(t1, t2)
        with db.engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM assignment_claim_invites WHERE assignment_id = :aid"),
                {"aid": aid},
            ).scalar()
        self.assertEqual(int(n or 0), 1)

    def test_create_assignment_rejects_unknown_employee_contact_id(self):
        db = self.db
        _seed_company(db, "co-uni-5", "Uni Co 5")
        hr = "hr-uni-5"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-uni-5")
        with self.assertRaises(ValueError) as ctx:
            db.create_assignment(
                assignment_id=str(uuid.uuid4()),
                case_id=case_id,
                hr_user_id=hr,
                employee_user_id=None,
                employee_identifier="x@unico.example",
                status="assigned",
                employee_contact_id="00000000-0000-0000-0000-000000000099",
            )
        self.assertIn("employee_contact_id not found", str(ctx.exception))

    def test_at_most_one_pending_claim_invite_per_assignment_index(self):
        db = self.db
        _seed_company(db, "co-uni-6", "Uni Co 6")
        hr = "hr-uni-6"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-uni-6")
        aid = str(uuid.uuid4())
        ecid = db.resolve_or_create_employee_contact(
            "co-uni-6",
            "one.pending@unico.example",
            first_name=None,
            last_name=None,
            request_id=None,
        )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier="one.pending@unico.example",
            status="assigned",
            employee_contact_id=ecid,
        )
        db.ensure_pending_assignment_invites(
            aid, case_id, hr, ecid, "one.pending@unico.example", "one.pending@unico.example", request_id=None
        )
        tok2 = str(uuid.uuid4())
        with self.assertRaises(IntegrityError):
            db.create_assignment_invite(str(uuid.uuid4()), case_id, hr, "one.pending@unico.example", tok2)
            db.create_assignment_claim_invite(
                str(uuid.uuid4()),
                aid,
                ecid,
                tok2,
                email_normalized="one.pending@unico.example",
                request_id=None,
            )


if __name__ == "__main__":
    unittest.main()
