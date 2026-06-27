"""
DOCFLOW P1 — case-scoped document upload→satisfy loop (SQLite in-memory).

Covers:
  (a) POST /api/cases/{id}/documents uploads a file → 200 + a case_evidence row +
      a case_documents row with the right document_key.
  (b) the generalized sync maps a non-passport evidence_type (employment_letter) →
      case_documents.
  (c) _required_input_present('employment_letter', ctx) is True once a case_documents
      row exists.
  (d) GET returns the keyed required-docs list, including un-uploaded items as 'required'.

The root conftest mocks ``backend.database`` so unit tests don't open a real engine; this
file needs a real (in-memory SQLite) Database, so it restores the real module first, then
swaps the engine in — the same pattern the passport-sync test uses.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

# ── Restore the REAL backend.database (root conftest installs a MagicMock) ──────
sys.modules.pop("backend.database", None)
import backend.database as dbmod  # noqa: E402  (real module)
from backend.database import Database  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app.services.passport_case_document_sync_service import (  # noqa: E402
    ensure_case_document_for_key,
)
from backend.relocation_plan_status_derivation import (  # noqa: E402
    RelocationPlanDerivationContext,
)
from backend.app.services.relocation_plan_view_service import (  # noqa: E402
    _required_input_present,
)


def _fresh_db() -> Database:
    # StaticPool: share ONE in-memory connection across threads so the TestClient
    # worker thread sees the schema + rows seeded on the main thread.
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    dbmod._engine = eng
    dbmod._is_sqlite = True
    db = Database()
    db.ensure_initialized()
    # The bundled SQLite CREATE for case_milestones predates the source/service_key
    # columns that list_case_milestones / upsert_case_milestone reference. Add them so
    # the milestone-backed plan view works under the test harness.
    with db.engine.begin() as conn:
        for col in ("source", "service_key"):
            try:
                conn.execute(text(f"ALTER TABLE case_milestones ADD COLUMN {col} TEXT"))
            except Exception:
                pass
    return db


def _seed_graph(db: Database) -> tuple[str, str, str, str]:
    """Direct-INSERT the minimal graph: company, assignment, mobility case + link,
    employee person. (Avoids db.create_case / create_assignment, whose
    get_case_by_id uses a Postgres-only ``id::text`` cast that SQLite rejects.)

    Returns (assignment_id, case_id, hr, emp). The mobility case id == case_id so a
    single id threads case_evidence (by case_id) and case_documents (by mobility id).
    """
    now = datetime.utcnow().isoformat()
    company_id = str(uuid.uuid4())
    hr = str(uuid.uuid4())
    emp = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    mid = str(uuid.uuid4())
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": "DocFlow Co", "ca": now},
        )
        conn.execute(
            text(
                "INSERT INTO case_assignments "
                "(id, case_id, canonical_case_id, hr_user_id, employee_user_id, employee_identifier, "
                " status, created_at, updated_at, intake_step, intake_total_steps) "
                "VALUES (:id, :cid, :cid, :hr, :emp, :ident, 'assigned', :ca, :ca, 0, 1)"
            ),
            {"id": aid, "cid": case_id, "hr": hr, "emp": emp, "ident": "docflow@example.com", "ca": now},
        )
        conn.execute(
            text(
                "INSERT INTO mobility_cases (id, company_id, employee_user_id, metadata, created_at, updated_at) "
                "VALUES (:id, :co, :emp, '{}', :ca, :ca)"
            ),
            {"id": mid, "co": company_id, "emp": emp, "ca": now},
        )
        conn.execute(
            text(
                "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                "VALUES (:id, :aid, :mid, :ca, :ca)"
            ),
            {"id": str(uuid.uuid4()), "aid": aid, "mid": mid, "ca": now},
        )
        conn.execute(
            text(
                "INSERT INTO case_people (id, case_id, role, metadata, created_at, updated_at) "
                "VALUES (:id, :mid, 'employee', '{}', :ca, :ca)"
            ),
            {"id": str(uuid.uuid4()), "mid": mid, "ca": now},
        )
    return aid, case_id, hr, emp


def _mobility_case_id(db: Database, aid: str) -> str:
    with db.engine.connect() as conn:
        return conn.execute(
            text("SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :a"),
            {"a": aid},
        ).scalar()


# ── (b) generalized sync ───────────────────────────────────────────────────────
class GeneralizedSyncTests(unittest.TestCase):
    def test_non_passport_evidence_creates_case_document(self) -> None:
        db = _fresh_db()
        aid, case_id, _hr, _emp = _seed_graph(db)
        eid = db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="employment_letter",
            file_url="https://storage.example/letter.pdf",
            status="submitted",
        )
        did = ensure_case_document_for_key(db, aid, "employment_letter")
        self.assertIsNotNone(did)
        mid = _mobility_case_id(db, aid)
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT document_key, document_status, metadata FROM case_documents "
                    "WHERE case_id = :c AND document_key = :dk"
                ),
                {"c": mid, "dk": "employment_letter"},
            ).mappings().first()
        self.assertIsNotNone(row)
        self.assertEqual(row["document_key"], "employment_letter")
        self.assertEqual(row["document_status"], "uploaded")
        self.assertEqual(json.loads(row["metadata"]).get("case_evidence_id"), eid)

    def test_alias_evidence_type_folds_to_canonical_key(self) -> None:
        db = _fresh_db()
        aid, case_id, _hr, _emp = _seed_graph(db)
        db.insert_case_evidence(
            case_id=case_id,
            assignment_id=aid,
            participant_id=None,
            requirement_id=None,
            evidence_type="employment_contract",  # alias → employment_letter
            status="submitted",
        )
        did = ensure_case_document_for_key(db, aid, "employment_letter")
        self.assertIsNotNone(did)


# ── (c) generalized satisfaction ───────────────────────────────────────────────
class SatisfactionTests(unittest.TestCase):
    def test_required_input_present_via_case_documents(self) -> None:
        ctx = RelocationPlanDerivationContext(
            case_documents=[
                {"document_key": "employment_letter", "document_status": "uploaded"}
            ]
        )
        self.assertTrue(_required_input_present("employment_letter", ctx))

    def test_required_input_absent_without_upload(self) -> None:
        ctx = RelocationPlanDerivationContext(case_documents=[])
        self.assertFalse(_required_input_present("employment_letter", ctx))
        self.assertFalse(_required_input_present("income_proof", ctx))

    def test_arbitrary_key_satisfied_by_matching_document(self) -> None:
        ctx = RelocationPlanDerivationContext(
            case_documents=[{"document_key": "income_proof", "document_status": "approved"}]
        )
        self.assertTrue(_required_input_present("income_proof", ctx))
        # A different key is not satisfied by this row.
        self.assertFalse(_required_input_present("accommodation_proof_nl", ctx))


# ── (a) + (d) HTTP endpoints ───────────────────────────────────────────────────
_USER = {"id": "emp-1", "role": "EMPLOYEE", "email": "docflow@example.com"}


def _make_app(router_module):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router_module.router)
    app.dependency_overrides[router_module.get_current_user] = lambda: _USER
    return app


class CaseDocumentsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        import backend.app.routers.case_documents as cdoc

        self.cdoc = cdoc
        self.db = _fresh_db()
        # Point the router's singleton at our in-memory db.
        self._prev_main_db = cdoc.main_db
        cdoc.main_db = self.db
        # Case-access check is exercised elsewhere; stub it here so the test focuses
        # on the upload→satisfy mechanics (no real cases/case_assignments auth rows).
        self._prev_access = cdoc._assert_case_access
        cdoc._assert_case_access = lambda user, case_id: None
        self.client = TestClient(_make_app(cdoc), raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.cdoc.main_db = self._prev_main_db
        self.cdoc._assert_case_access = self._prev_access

    def _fake_supabase(self):
        sb = MagicMock()
        sb.storage.from_.return_value.upload.return_value = None
        return sb

    def test_post_upload_creates_evidence_and_document(self) -> None:
        aid, case_id, _hr, _emp = _seed_graph(self.db)
        with patch(
            "backend.app.services.supabase_client.get_supabase_admin_client",
            return_value=self._fake_supabase(),
        ):
            resp = self.client.post(
                f"/api/cases/{case_id}/documents",
                files={"file": ("letter.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"document_key": "employment_letter"},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["document_key"], "employment_letter")
        self.assertEqual(body["document_status"], "uploaded")
        self.assertTrue(body["file_url"].startswith(f"case-docs/{case_id}/employment_letter/"))

        # case_evidence row exists with the right evidence_type.
        with self.db.engine.connect() as conn:
            ev = conn.execute(
                text(
                    "SELECT evidence_type, file_url, status FROM case_evidence "
                    "WHERE assignment_id = :a"
                ),
                {"a": aid},
            ).mappings().first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev["evidence_type"], "employment_letter")
        self.assertEqual(ev["status"], "submitted")

        # case_documents row exists with the right document_key.
        mid = _mobility_case_id(self.db, aid)
        with self.db.engine.connect() as conn:
            doc = conn.execute(
                text(
                    "SELECT document_key, document_status FROM case_documents "
                    "WHERE case_id = :c AND document_key = :dk"
                ),
                {"c": mid, "dk": "employment_letter"},
            ).mappings().first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc["document_status"], "uploaded")

    def test_post_rejects_unsupported_mime(self) -> None:
        _aid, case_id, _hr, _emp = _seed_graph(self.db)
        with patch(
            "backend.app.services.supabase_client.get_supabase_admin_client",
            return_value=self._fake_supabase(),
        ):
            resp = self.client.post(
                f"/api/cases/{case_id}/documents",
                files={"file": ("note.txt", b"hello", "text/plain")},
                data={"document_key": "income_proof"},
            )
        self.assertEqual(resp.status_code, 415, resp.text)

    def test_get_lists_required_docs_with_required_status(self) -> None:
        aid, case_id, _hr, _emp = _seed_graph(self.db)
        # Seed the two document-bearing roadmap tasks as milestones.
        self.db.upsert_case_milestone(
            case_id=case_id, milestone_type="task_passport_upload",
            title="Upload passport copy", status="pending", sort_order=10,
        )
        self.db.upsert_case_milestone(
            case_id=case_id, milestone_type="task_employment_letter",
            title="Upload employment letter", status="pending", sort_order=20,
        )
        # Upload only the employment letter (via the sync path).
        self.db.insert_case_evidence(
            case_id=case_id, assignment_id=aid, participant_id=None, requirement_id=None,
            evidence_type="employment_letter", file_url="case-docs/x/employment_letter/f.pdf",
            status="submitted",
        )
        ensure_case_document_for_key(self.db, aid, "employment_letter")

        resp = self.client.get(f"/api/cases/{case_id}/documents")
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()
        by_key = {it["key"]: it for it in items}
        self.assertIn("passport_copy", by_key)
        self.assertIn("employment_letter", by_key)
        # passport not uploaded → 'required'; employment uploaded → 'uploaded'.
        self.assertEqual(by_key["passport_copy"]["status"], "required")
        self.assertEqual(by_key["employment_letter"]["status"], "uploaded")
        self.assertEqual(
            by_key["employment_letter"]["file_url"], "case-docs/x/employment_letter/f.pdf"
        )


if __name__ == "__main__":
    unittest.main()
