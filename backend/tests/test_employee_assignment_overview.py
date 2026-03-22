"""Employee assignment overview service (linked + pending summaries)."""
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
from backend.services.employee_assignment_overview import (
    build_employee_assignment_overview,
    _claim_summary,
)


def _norm_status(s):
    return (s or "created").strip().lower()


def _seed_company(db: Database, company_id: str, name: str = "Test Co") -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": name, "ca": now},
        )


class EmployeeAssignmentOverviewTests(unittest.TestCase):
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

    def test_linked_includes_company_destination_and_stage(self):
        db = self.db
        _seed_company(db, "co-ov-1", "Acme Corp")
        hr = "hr-ov-1"
        emp = str(uuid.uuid4())
        case_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        db.create_case(case_id, hr, {"origin": "NO", "destination": "DE"}, company_id="co-ov-1")
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE relocation_cases SET host_country = :h, home_country = :o, stage = :st "
                    "WHERE id = :cid"
                ),
                {"h": "Germany", "o": "Norway", "st": "intake", "cid": case_id},
            )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=emp,
            employee_identifier="e1@example.com",
            status="assigned",
        )
        out = build_employee_assignment_overview(
            db, emp, request_id=None, normalize_assignment_status=_norm_status
        )
        self.assertEqual(len(out["linked"]), 1)
        row = out["linked"][0]
        self.assertEqual(row["assignment_id"], aid)
        self.assertEqual(row["case_id"], case_id)
        self.assertEqual(row["company"]["id"], "co-ov-1")
        self.assertEqual(row["company"]["name"], "Acme Corp")
        self.assertEqual(row["destination"]["label"], "Norway → Germany")
        self.assertEqual(row["current_stage"], "intake")
        self.assertIn("created_at", row)
        self.assertIn("updated_at", row)

    def test_pending_shows_claim_state_and_respects_company_match(self):
        db = self.db
        _seed_company(db, "co-ov-2a", "Co A")
        _seed_company(db, "co-ov-2b", "Co B")
        hr = "hr-ov-2"
        emp = str(uuid.uuid4())
        self.assertTrue(db.create_user(emp, None, "pending.ov@example.com", "h", "EMPLOYEE", "P"))

        case_ok = str(uuid.uuid4())
        db.create_case(case_ok, hr, {}, company_id="co-ov-2a")
        ec_ok = str(uuid.uuid4())
        aid_ok = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "linked_auth_user_id, created_at, updated_at) "
                    "VALUES (:id, :cid, :ik, :en, :uid, :ca, :ua)"
                ),
                {
                    "id": ec_ok,
                    "cid": "co-ov-2a",
                    "ik": "pending.ov@example.com",
                    "en": "pending.ov@example.com",
                    "uid": emp,
                    "ca": now,
                    "ua": now,
                },
            )
        db.create_assignment(
            assignment_id=aid_ok,
            case_id=case_ok,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier="pending.ov@example.com",
            status="assigned",
            employee_contact_id=ec_ok,
            employee_link_mode="pending_claim",
        )
        tok = str(uuid.uuid4())
        db.ensure_pending_assignment_invites(
            aid_ok, case_ok, hr, ec_ok, "pending.ov@example.com", "pending.ov@example.com", request_id=None
        )

        case_bad = str(uuid.uuid4())
        db.create_case(case_bad, hr, {}, company_id="co-ov-2b")
        aid_bad = str(uuid.uuid4())
        # Same contact (company co-ov-2a) but case row tied to another company → excluded from overview.
        db.create_assignment(
            assignment_id=aid_bad,
            case_id=case_bad,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier="pending.ov@example.com",
            status="assigned",
            employee_contact_id=ec_ok,
            employee_link_mode="pending_claim",
        )

        out = build_employee_assignment_overview(
            db, emp, request_id=None, normalize_assignment_status=_norm_status
        )
        pending_ids = {p["assignment_id"] for p in out["pending"]}
        self.assertIn(aid_ok, pending_ids)
        self.assertNotIn(aid_bad, pending_ids)
        p0 = next(p for p in out["pending"] if p["assignment_id"] == aid_ok)
        self.assertEqual(p0["claim"]["state"], "invite_pending")
        self.assertTrue(p0["claim"]["requires_explicit_claim"])
        self.assertFalse(p0["claim"]["extra_verification_required"])

    def test_claim_summary_revoked(self):
        s = _claim_summary(["revoked", "revoked"])
        self.assertEqual(s["state"], "invite_revoked")
        self.assertTrue(s["extra_verification_required"])

    def test_map_claim_invite_statuses_bulk(self):
        db = self.db
        _seed_company(db, "co-ov-3")
        hr = "hr-ov-3"
        case_id = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id="co-ov-3")
        ec = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO employee_contacts (id, company_id, invite_key, email_normalized, "
                    "created_at, updated_at) VALUES (:id, :cid, :ik, :en, :ca, :ua)"
                ),
                {"id": ec, "cid": "co-ov-3", "ik": "x@ov3.example", "en": "x@ov3.example", "ca": now, "ua": now},
            )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier="x@ov3.example",
            status="assigned",
            employee_contact_id=ec,
        )
        db.create_assignment_claim_invite(
            str(uuid.uuid4()), aid, ec, str(uuid.uuid4()), email_normalized="x@ov3.example", request_id=None
        )
        m = db.map_claim_invite_statuses_by_assignments([aid, "missing-id"], request_id=None)
        self.assertIn(aid, m)
        self.assertIn("pending", m[aid])


if __name__ == "__main__":
    unittest.main()
