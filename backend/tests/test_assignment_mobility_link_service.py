"""assignment_mobility_links + ensure_mobility_case_link_for_assignment (SQLite in-memory)."""
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
from backend.services.assignment_mobility_link_service import ensure_mobility_case_link_for_assignment


def _seed_company(db: Database, company_id: str) -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": "Link Test Co", "ca": now},
        )


class AssignmentMobilityLinkServiceTests(unittest.TestCase):
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

    def test_creates_link_and_mobility_case_when_none(self) -> None:
        db = self.db
        company_id = str(uuid.uuid4())
        _seed_company(db, company_id)
        hr = str(uuid.uuid4())
        emp = str(uuid.uuid4())
        case_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        db.create_case(case_id, hr, {"origin": "NO", "destination": "DE"}, company_id=company_id)
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE relocation_cases SET host_country = :h, home_country = :o WHERE id = :cid"
                ),
                {"h": "Germany", "o": "Norway", "cid": case_id},
            )
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=emp,
            employee_identifier="e@example.com",
            status="assigned",
        )
        mid = ensure_mobility_case_link_for_assignment(db, aid)
        self.assertIsNotNone(mid)
        assert mid is not None
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT assignment_id, mobility_case_id, origin_country, destination_country "
                    "FROM assignment_mobility_links aml "
                    "JOIN mobility_cases mc ON mc.id = aml.mobility_case_id "
                    "WHERE aml.assignment_id = :aid"
                ),
                {"aid": aid},
            ).mappings().first()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["assignment_id"], aid)
        self.assertEqual(str(row["mobility_case_id"]), mid)
        self.assertEqual(row["origin_country"], "Norway")
        self.assertEqual(row["destination_country"], "Germany")

    def test_idempotent_second_call(self) -> None:
        db = self.db
        company_id = str(uuid.uuid4())
        _seed_company(db, company_id)
        hr = str(uuid.uuid4())
        case_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        db.create_case(case_id, hr, {}, company_id=company_id)
        db.create_assignment(
            assignment_id=aid,
            case_id=case_id,
            hr_user_id=hr,
            employee_user_id=None,
            employee_identifier="pending@example.com",
            status="assigned",
        )
        m1 = ensure_mobility_case_link_for_assignment(db, aid)
        m2 = ensure_mobility_case_link_for_assignment(db, aid)
        self.assertEqual(m1, m2)
        with db.engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) AS c FROM assignment_mobility_links WHERE assignment_id = :aid"),
                {"aid": aid},
            ).scalar()
        self.assertEqual(int(n), 1)

    def test_overview_flow_unbroken(self) -> None:
        """Existing assignment listing inputs still work after mobility link ensure."""
        db = self.db
        from backend.services.employee_assignment_overview import (
            build_employee_assignment_overview,
        )

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
            employee_identifier="x@example.com",
            status="assigned",
        )
        ensure_mobility_case_link_for_assignment(db, aid)
        out = build_employee_assignment_overview(db, emp, request_id=None, normalize_assignment_status=lambda s: (s or "").lower())
        self.assertEqual(len(out["linked"]), 1)
        self.assertEqual(out["linked"][0]["assignment_id"], aid)


if __name__ == "__main__":
    unittest.main()
