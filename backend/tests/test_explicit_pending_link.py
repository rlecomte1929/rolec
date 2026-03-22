"""Explicit pending assignment link (hub) — eligibility, idempotency, failure modes."""
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
from backend.services.explicit_pending_link_service import (
    evaluate_pending_explicit_link_eligibility,
    execute_pending_explicit_link,
    PENDING_LINK_COMPANY_MISMATCH,
    PENDING_LINK_CONTACT_NOT_LINKED,
    PENDING_LINK_EXTRA_VERIFICATION,
    PENDING_LINK_INVITE_REVOKED,
    PENDING_LINK_NOT_PENDING,
)


def _seed_company(db: Database, company_id: str, name: str = "Test Co") -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": name, "ca": now},
        )


class ExplicitPendingLinkTests(unittest.TestCase):
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

    def _seed_pending_row(self, db: Database, *, email: str, company_id: str, hr: str) -> tuple[str, str, str]:
        _seed_company(db, company_id)
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id=company_id)
        emp = str(uuid.uuid4())
        self.assertTrue(db.create_user(emp, None, email, "h", "EMPLOYEE", "P"))
        ec = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "linked_auth_user_id, created_at, updated_at) "
                    "VALUES (:id, :cid, :ik, :en, :uid, :ca, :ua)"
                ),
                {
                    "id": ec,
                    "cid": company_id,
                    "ik": email,
                    "en": email,
                    "uid": emp,
                    "ca": now,
                    "ua": now,
                },
            )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier=email,
            status="assigned",
            employee_contact_id=ec,
            employee_link_mode="pending_claim",
        )
        db.ensure_pending_assignment_invites(
            aid, case_id, hr, ec, email, email, request_id=None
        )
        return emp, aid, case_id

    def test_execute_links_and_idempotent(self):
        db = self.db
        hr = "hr-xpl-1"
        email = "explicit.pending@link.example"
        emp, aid, _case = self._seed_pending_row(db, email=email, company_id="co-xpl-1", hr=hr)
        idents = [email.lower()]

        self.assertEqual(
            evaluate_pending_explicit_link_eligibility(
                db, auth_user_id=emp, assignment_id=aid, user_identifiers=idents
            ),
            PENDING_LINK_ELIGIBLE,
        )

        r1 = execute_pending_explicit_link(
            db,
            auth_user_id=emp,
            assignment_id=aid,
            user_identifiers=idents,
        )
        self.assertTrue(r1["success"])
        self.assertFalse(r1.get("alreadyLinked"))
        self.assertEqual(db.get_assignment_by_id(aid).get("employee_user_id"), emp)
        self.assertFalse((db.get_assignment_by_id(aid).get("employee_link_mode") or "").strip())

        r2 = execute_pending_explicit_link(
            db,
            auth_user_id=emp,
            assignment_id=aid,
            user_identifiers=idents,
        )
        self.assertTrue(r2["success"])
        self.assertTrue(r2.get("alreadyLinked"))

    def test_company_mismatch_not_eligible(self):
        db = self.db
        _seed_company(db, "co-xpl-a")
        _seed_company(db, "co-xpl-b")
        hr = "hr-xpl-2"
        email = "mix.co@link.example"
        emp = str(uuid.uuid4())
        self.assertTrue(db.create_user(emp, None, email, "h", "EMPLOYEE", "P"))
        case_bad = str(uuid.uuid4())
        db.create_case(case_bad, hr, {}, company_id="co-xpl-b")
        ec = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "linked_auth_user_id, created_at, updated_at) "
                    "VALUES (:id, :cid, :ik, :en, :uid, :ca, :ua)"
                ),
                {
                    "id": ec,
                    "cid": "co-xpl-a",
                    "ik": email,
                    "en": email,
                    "uid": emp,
                    "ca": now,
                    "ua": now,
                },
            )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_bad,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier=email,
            status="assigned",
            employee_contact_id=ec,
            employee_link_mode="pending_claim",
        )
        db.ensure_pending_assignment_invites(aid, case_bad, hr, ec, email, email, request_id=None)

        out = evaluate_pending_explicit_link_eligibility(
            db, auth_user_id=emp, assignment_id=aid, user_identifiers=[email.lower()]
        )
        self.assertEqual(out, PENDING_LINK_COMPANY_MISMATCH)

    def test_not_pending_mode_rejected(self):
        db = self.db
        hr = "hr-xpl-3"
        email = "legacy.mode@link.example"
        _seed_company(db, "co-xpl-3")
        emp = str(uuid.uuid4())
        self.assertTrue(db.create_user(emp, None, email, "h", "EMPLOYEE", "P"))
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-xpl-3")
        ec = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "linked_auth_user_id, created_at, updated_at) "
                    "VALUES (:id, :cid, :ik, :en, :uid, :ca, :ua)"
                ),
                {
                    "id": ec,
                    "cid": "co-xpl-3",
                    "ik": email,
                    "en": email,
                    "uid": emp,
                    "ca": now,
                    "ua": now,
                },
            )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier=email,
            status="assigned",
            employee_contact_id=ec,
            employee_link_mode=None,
        )
        out = evaluate_pending_explicit_link_eligibility(
            db, auth_user_id=emp, assignment_id=aid, user_identifiers=[email.lower()]
        )
        self.assertEqual(out, PENDING_LINK_NOT_PENDING)

    def test_contact_not_linked_to_user(self):
        db = self.db
        hr = "hr-xpl-4"
        email = "nolink@link.example"
        emp = str(uuid.uuid4())
        self.assertTrue(db.create_user(emp, None, email, "h", "EMPLOYEE", "P"))
        _seed_company(db, "co-xpl-4")
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-xpl-4")
        ec = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "created_at, updated_at) "
                    "VALUES (:id, :cid, :ik, :en, :ca, :ua)"
                ),
                {"id": ec, "cid": "co-xpl-4", "ik": email, "en": email, "ca": now, "ua": now},
            )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier=email,
            status="assigned",
            employee_contact_id=ec,
            employee_link_mode="pending_claim",
        )
        out = evaluate_pending_explicit_link_eligibility(
            db, auth_user_id=emp, assignment_id=aid, user_identifiers=[email.lower()]
        )
        self.assertEqual(out, PENDING_LINK_CONTACT_NOT_LINKED)

    def test_revoked_invites_block(self):
        db = self.db
        hr = "hr-xpl-5"
        email = "revoked@link.example"
        emp, aid, _ = self._seed_pending_row(db, email=email, company_id="co-xpl-5", hr=hr)
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE assignment_claim_invites SET status = 'revoked' WHERE assignment_id = :aid"
                ),
                {"aid": aid},
            )
        out = evaluate_pending_explicit_link_eligibility(
            db, auth_user_id=emp, assignment_id=aid, user_identifiers=[email.lower()]
        )
        self.assertEqual(out, PENDING_LINK_INVITE_REVOKED)

    def test_nonstandard_invite_status_requires_extra_verification(self):
        db = self.db
        hr = "hr-xpl-6"
        email = "weird@link.example"
        emp, aid, _ = self._seed_pending_row(db, email=email, company_id="co-xpl-6", hr=hr)
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE assignment_claim_invites SET status = 'on_hold' WHERE assignment_id = :aid"
                ),
                {"aid": aid},
            )
        out = evaluate_pending_explicit_link_eligibility(
            db, auth_user_id=emp, assignment_id=aid, user_identifiers=[email.lower()]
        )
        self.assertEqual(out, PENDING_LINK_EXTRA_VERIFICATION)


if __name__ == "__main__":
    unittest.main()
