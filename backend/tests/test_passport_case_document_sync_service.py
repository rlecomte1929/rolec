"""passport case_evidence -> case_documents sync (SQLite in-memory)."""
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
from backend.services.passport_case_document_sync_service import (
    GRAPH_PASSPORT_DOCUMENT_KEY,
    ensure_passport_case_document_for_assignment,
    map_case_evidence_status_to_document_status,
)


def _seed_company(db: Database, company_id: str) -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": "Doc Sync Co", "ca": now},
        )


class PassportCaseDocumentSyncTests(unittest.TestCase):
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

    def _seed_graph(self, db: Database) -> tuple[str, str, str, str]:
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
            employee_identifier="doc@example.com",
            status="assigned",
        )
        ensure_mobility_case_link_for_assignment(db, aid)
        ensure_employee_case_person_for_assignment(db, aid)
        return aid, case_id, hr, emp

    def test_passport_evidence_creates_graph_document(self) -> None:
        db = self.db
        aid, case_id, _hr, _emp = self._seed_graph(db)
        eid = db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="passport_scan",
            file_url="https://storage.example/p.pdf",
            metadata={"uploaded_by": "test"},
            status="submitted",
        )
        did = ensure_passport_case_document_for_assignment(db, aid)
        self.assertIsNotNone(did)
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT document_key, document_status, metadata, person_id FROM case_documents "
                    "WHERE id = :id"
                ),
                {"id": did},
            ).mappings().first()
        assert row is not None
        self.assertEqual(row["document_key"], GRAPH_PASSPORT_DOCUMENT_KEY)
        self.assertEqual(row["document_status"], "uploaded")
        meta = json.loads(row["metadata"])
        self.assertEqual(meta.get("case_evidence_id"), eid)
        self.assertEqual(meta.get("file_url"), "https://storage.example/p.pdf")
        self.assertIsNotNone(row["person_id"])

    def test_repeated_sync_single_row(self) -> None:
        db = self.db
        aid, case_id, _hr, _emp = self._seed_graph(db)
        db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="passport_copy",
            file_url=None,
            status="submitted",
        )
        d1 = ensure_passport_case_document_for_assignment(db, aid)
        d2 = ensure_passport_case_document_for_assignment(db, aid)
        self.assertEqual(d1, d2)
        with db.engine.connect() as conn:
            mid = conn.execute(
                text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :a"),
                {"a": aid},
            ).scalar()
            n2 = conn.execute(
                text("SELECT COUNT(*) FROM case_documents WHERE case_id = :c AND document_key = :dk"),
                {"c": mid, "dk": GRAPH_PASSPORT_DOCUMENT_KEY},
            ).scalar()
        self.assertEqual(int(n2), 1)

    def test_evidence_status_update_updates_graph(self) -> None:
        db = self.db
        aid, case_id, _hr, _emp = self._seed_graph(db)
        eid = db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="doc_passport",
            file_url=None,
            status="submitted",
        )
        ensure_passport_case_document_for_assignment(db, aid)
        with db.engine.begin() as conn:
            conn.execute(
                text("UPDATE case_evidence SET status = 'verified' WHERE id = :id"),
                {"id": eid},
            )
        ensure_passport_case_document_for_assignment(db, aid)
        with db.engine.connect() as conn:
            mid = conn.execute(
                text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :a"),
                {"a": aid},
            ).scalar()
            st = conn.execute(
                text(
                    "SELECT document_status FROM case_documents WHERE case_id = :c AND document_key = :dk"
                ),
                {"c": mid, "dk": GRAPH_PASSPORT_DOCUMENT_KEY},
            ).scalar()
        self.assertEqual(st, "approved")

    def test_newest_passport_wins_when_multiple(self) -> None:
        db = self.db
        aid, case_id, _hr, _emp = self._seed_graph(db)
        db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="passport_scan",
            file_url="https://old.example/1.pdf",
            status="submitted",
        )
        newer = db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="passport_copy",
            file_url="https://new.example/2.pdf",
            status="submitted",
        )
        ensure_passport_case_document_for_assignment(db, aid)
        with db.engine.connect() as conn:
            mid = conn.execute(
                text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :a"),
                {"a": aid},
            ).scalar()
            meta = conn.execute(
                text("SELECT metadata FROM case_documents WHERE case_id = :c AND document_key = :dk"),
                {"c": mid, "dk": GRAPH_PASSPORT_DOCUMENT_KEY},
            ).scalar()
        self.assertEqual(json.loads(meta).get("case_evidence_id"), newer)

    def test_unrelated_evidence_ignored(self) -> None:
        db = self.db
        aid, case_id, _hr, _emp = self._seed_graph(db)
        db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="employment_contract",
            file_url=None,
            status="submitted",
        )
        out = ensure_passport_case_document_for_assignment(db, aid)
        self.assertIsNone(out)
        with db.engine.connect() as conn:
            mid = conn.execute(
                text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :a"),
                {"a": aid},
            ).scalar()
            n = conn.execute(text("SELECT COUNT(*) FROM case_documents WHERE case_id = :c"), {"c": mid}).scalar()
        self.assertEqual(int(n), 0)

    def test_missing_passport_evidence_returns_none_without_error(self) -> None:
        db = self.db
        aid, _, _, _ = self._seed_graph(db)
        self.assertIsNone(ensure_passport_case_document_for_assignment(db, aid))

    def test_bridge_and_person_sync_unaffected(self) -> None:
        db = self.db
        aid, case_id, _hr, emp = self._seed_graph(db)
        db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="passport",
            status="submitted",
        )
        ensure_passport_case_document_for_assignment(db, aid)
        with db.engine.connect() as conn:
            m = conn.execute(
                text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :a"),
                {"a": aid},
            ).mappings().first()
            p = conn.execute(
                text("SELECT id FROM case_people WHERE case_id = :c AND role = 'employee'"),
                {"c": m["mobility_case_id"]},
            ).fetchone()
        self.assertIsNotNone(m)
        self.assertIsNotNone(p)

    def test_status_mapping(self) -> None:
        self.assertEqual(map_case_evidence_status_to_document_status("submitted"), "uploaded")
        self.assertEqual(map_case_evidence_status_to_document_status("verified"), "approved")
        self.assertEqual(map_case_evidence_status_to_document_status("rejected"), "rejected")


if __name__ == "__main__":
    unittest.main()
