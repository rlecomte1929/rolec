"""ensure_employee_case_person_for_assignment — SQLite in-memory."""
from __future__ import annotations

import json
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
from backend.services.assignment_mobility_link_service import ensure_mobility_case_link_for_assignment
from backend.services.employee_case_person_service import ensure_employee_case_person_for_assignment


def _seed_company(db: Database, company_id: str) -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": "Person Sync Co", "ca": now},
        )


class EmployeeCasePersonServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self._prev_engine = dbmod._engine
        self._prev_sqlite = dbmod._is_sqlite
        dbmod._engine = eng
        dbmod._is_sqlite = True
        self.db = Database()

    def tearDown(self) -> None:
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def _seed_assignment_with_link(self, db: Database) -> tuple[str, str, str]:
        company_id = str(uuid.uuid4())
        _seed_company(db, company_id)
        hr = str(uuid.uuid4())
        emp = str(uuid.uuid4())
        case_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id=company_id)
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=emp,
            employee_identifier="sync@example.com",
            status="assigned",
            employee_first_name="Pat",
            employee_last_name="Lee",
        )
        mid = ensure_mobility_case_link_for_assignment(db, aid)
        self.assertIsNotNone(mid)
        assert mid is not None
        return aid, mid, emp

    def test_creates_employee_row_when_missing(self) -> None:
        db = self.db
        aid, mid, _emp = self._seed_assignment_with_link(db)
        db.save_employee_profile(
            aid,
            {
                "employeeProfile": {
                    "fullName": "Pat Lee",
                    "email": "sync@example.com",
                    "nationality": "NO",
                    "residenceCountry": "NO",
                },
                "familyMembers": {"maritalStatus": "single"},
            },
        )
        pid = ensure_employee_case_person_for_assignment(db, aid)
        self.assertIsNotNone(pid)
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, role, metadata FROM case_people WHERE case_id = :cid AND role = 'employee'"
                ),
                {"cid": mid},
            ).mappings().first()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["role"], "employee")
        meta = json.loads(row["metadata"])
        self.assertEqual(meta.get("full_name"), "Pat Lee")
        self.assertEqual(meta.get("email"), "sync@example.com")
        self.assertEqual(meta.get("nationality"), "NO")
        self.assertEqual(meta.get("relationship_status"), "single")

    def test_idempotent_no_duplicate_row(self) -> None:
        db = self.db
        aid, mid, _ = self._seed_assignment_with_link(db)
        db.save_employee_profile(aid, {"employeeProfile": {"fullName": "A"}})
        p1 = ensure_employee_case_person_for_assignment(db, aid)
        p2 = ensure_employee_case_person_for_assignment(db, aid)
        self.assertEqual(p1, p2)
        with db.engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) AS c FROM case_people WHERE case_id = :cid AND role = 'employee'"),
                {"cid": mid},
            ).scalar()
        self.assertEqual(int(n), 1)

    def test_profile_update_refreshes_metadata(self) -> None:
        db = self.db
        aid, _mid, _ = self._seed_assignment_with_link(db)
        db.save_employee_profile(aid, {"employeeProfile": {"fullName": "Old"}})
        ensure_employee_case_person_for_assignment(db, aid)
        db.save_employee_profile(aid, {"employeeProfile": {"fullName": "New", "email": "n@example.com"}})
        ensure_employee_case_person_for_assignment(db, aid)
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT metadata FROM case_people WHERE case_id = (SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :aid) AND role = 'employee'"),
                {"aid": aid},
            ).mappings().first()
        assert row is not None
        meta = json.loads(row["metadata"])
        self.assertEqual(meta.get("full_name"), "New")
        self.assertEqual(meta.get("email"), "n@example.com")

    def test_missing_optional_fields_still_succeeds(self) -> None:
        db = self.db
        aid, mid, _ = self._seed_assignment_with_link(db)
        pid = ensure_employee_case_person_for_assignment(db, aid)
        self.assertIsNotNone(pid)
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT metadata FROM case_people WHERE case_id = :cid AND role = 'employee'"),
                {"cid": mid},
            ).mappings().first()
        assert row is not None
        self.assertEqual(json.loads(row["metadata"]).get("full_name"), "Pat Lee")

    def test_mobility_bridge_still_works(self) -> None:
        db = self.db
        aid, mid, _ = self._seed_assignment_with_link(db)
        self.assertTrue(mid)
        ensure_employee_case_person_for_assignment(db, aid)
        with db.engine.connect() as conn:
            r = conn.execute(
                text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :aid"),
                {"aid": aid},
            ).mappings().first()
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(str(r["mobility_case_id"]), mid)


if __name__ == "__main__":
    unittest.main()
