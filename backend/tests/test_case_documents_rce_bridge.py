"""AIQ-1780 — the case-document upload path must bridge into the rce case engine.

Guards the fix for a silent, total outage: every registered extraction agent sat at
zero `agent_runs` in production because the upload path users actually reach
(roadmap task CTA → /employee/case/:caseId/documents → POST /api/cases/{id}/documents)
never called `bridge_case_document_to_rce`. Only the *immigration* upload endpoint
bridged, and its UI has no inbound nav links, so it had never received an upload.

The load-bearing assertion is `test_bridge_receives_canonical_case_id_not_mobility_id`.
The handler has BOTH ids in scope — `eff_case_id` (canonical/relocation, what rce.cases
is keyed on) and `mobility_case_id` (per-assignment anchor, what case_documents is keyed
on, resolved two lines later). Passing the wrong one still returns 200 and still writes
case_documents; it just makes `_case_exists()` miss for every upload, forever, because
mobility_cases ids have no FK path to public.cases. That failure is invisible from the
response, which is exactly why it needs a test rather than review attention.

SQLite in-memory, same harness shape as test_case_documents_flow.py.
"""
from __future__ import annotations

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


_USER = {"id": "emp-1", "role": "EMPLOYEE", "email": "bridge@example.com"}


def _fresh_db() -> Database:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    dbmod._engine = eng
    dbmod._is_sqlite = True
    db = Database()
    db.ensure_initialized()
    return db


def _seed_graph(db: Database) -> tuple[str, str, str]:
    """Minimal graph. Returns (assignment_id, canonical_case_id, mobility_case_id).

    The two ids are deliberately DIFFERENT uuids — that is what lets the tests below
    tell which one the handler handed to the bridge.
    """
    now = datetime.utcnow().isoformat()
    company_id = str(uuid.uuid4())
    emp = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    mid = str(uuid.uuid4())
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": "Bridge Co", "ca": now},
        )
        conn.execute(
            text(
                "INSERT INTO case_assignments "
                "(id, case_id, canonical_case_id, hr_user_id, employee_user_id, "
                " employee_identifier, status, created_at, updated_at, intake_step, "
                " intake_total_steps) "
                "VALUES (:id, :cid, :cid, :hr, :emp, :ident, 'assigned', :ca, :ca, 0, 1)"
            ),
            {
                "id": aid, "cid": case_id, "hr": str(uuid.uuid4()), "emp": emp,
                "ident": "bridge@example.com", "ca": now,
            },
        )
        conn.execute(
            text(
                "INSERT INTO mobility_cases (id, company_id, employee_user_id, metadata, "
                "created_at, updated_at) VALUES (:id, :co, :emp, '{}', :ca, :ca)"
            ),
            {"id": mid, "co": company_id, "emp": emp, "ca": now},
        )
        conn.execute(
            text(
                "INSERT INTO assignment_mobility_links "
                "(id, assignment_id, mobility_case_id, created_at, updated_at) "
                "VALUES (:id, :aid, :mid, :ca, :ca)"
            ),
            {"id": str(uuid.uuid4()), "aid": aid, "mid": mid, "ca": now},
        )
    return aid, case_id, mid


def _make_app(router_module):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router_module.router)
    app.dependency_overrides[router_module.get_current_user] = lambda: _USER
    return app


class CaseDocumentRceBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        import backend.app.routers.case_documents as cdoc

        self.cdoc = cdoc
        self.db = _fresh_db()
        self._prev_main_db = cdoc.main_db
        cdoc.main_db = self.db
        self._prev_access = cdoc._assert_case_access
        cdoc._assert_case_access = lambda user, case_id: None
        self.client = TestClient(_make_app(cdoc), raise_server_exceptions=False)
        self.aid, self.case_id, self.mobility_id = _seed_graph(self.db)

    def tearDown(self) -> None:
        self.cdoc.main_db = self._prev_main_db
        self.cdoc._assert_case_access = self._prev_access

    def _fake_supabase(self):
        sb = MagicMock()
        sb.storage.from_.return_value.upload.return_value = None
        return sb

    def _upload(self, bridge_mock, pipeline_mock=None):
        """POST a PDF with the bridge (and optionally the pipeline) patched."""
        import backend.app.services.rce_pipeline_worker as worker

        stack = [
            patch(
                "backend.app.services.supabase_client.get_supabase_admin_client",
                return_value=self._fake_supabase(),
            ),
            patch.object(self.cdoc, "bridge_case_document_to_rce", bridge_mock),
            patch.object(worker, "process_rce_document", pipeline_mock or MagicMock()),
        ]
        for ctx in stack:
            ctx.start()
        try:
            return self.client.post(
                f"/api/cases/{self.case_id}/documents",
                files={"file": ("contract.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"document_key": "employment_letter"},
            )
        finally:
            for ctx in reversed(stack):
                ctx.stop()

    # ── the load-bearing test ──────────────────────────────────────────────────

    def test_bridge_receives_canonical_case_id_not_mobility_id(self) -> None:
        """The one argument that decides whether extraction ever runs."""
        bridge = MagicMock(return_value=None)
        resp = self._upload(bridge)
        self.assertEqual(resp.status_code, 200, resp.text)

        bridge.assert_called_once()
        passed = bridge.call_args.kwargs["case_id"]
        self.assertEqual(
            passed,
            self.case_id,
            "bridge must receive the canonical/relocation case id (rce.cases is keyed on it)",
        )
        self.assertNotEqual(
            passed,
            self.mobility_id,
            "passing the mobility_cases id makes _case_exists() miss on every upload, "
            "silently and forever — this is the regression being guarded",
        )

    def test_bridge_receives_the_uploaded_bytes_and_metadata(self) -> None:
        bridge = MagicMock(return_value=None)
        self._upload(bridge)

        kwargs = bridge.call_args.kwargs
        self.assertEqual(kwargs["content"], b"%PDF-1.4 fake")
        self.assertEqual(kwargs["mime_type"], "application/pdf")
        self.assertEqual(kwargs["original_filename"], "contract.pdf")
        self.assertEqual(kwargs["uploaded_by"], _USER["id"])
        self.assertTrue(
            kwargs["storage_uri"].startswith(f"case-docs/{self.case_id}/employment_letter/")
        )

    # ── pipeline scheduling ────────────────────────────────────────────────────

    def test_pipeline_is_scheduled_when_the_bridge_ingests(self) -> None:
        rce_doc_id = str(uuid.uuid4())
        pipeline = MagicMock()
        resp = self._upload(MagicMock(return_value=rce_doc_id), pipeline)

        self.assertEqual(resp.status_code, 200, resp.text)
        pipeline.assert_called_once_with(rce_doc_id)

    def test_pipeline_is_not_scheduled_when_the_bridge_skips(self) -> None:
        """None = case not in rce.cases, or the document is already ingested."""
        pipeline = MagicMock()
        resp = self._upload(MagicMock(return_value=None), pipeline)

        self.assertEqual(resp.status_code, 200, resp.text)
        pipeline.assert_not_called()

    # ── fail-soft contract ─────────────────────────────────────────────────────

    def test_bridge_failure_never_breaks_the_upload(self) -> None:
        """bridge_case_document_to_rce swallows its own errors, but if that contract
        ever regresses the upload must still succeed — extraction is best-effort and
        must never cost a user their document."""
        pipeline = MagicMock()
        resp = self._upload(MagicMock(side_effect=RuntimeError("rce down")), pipeline)

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["document_key"], "employment_letter")
        pipeline.assert_not_called()

        # The primary write still happened.
        with self.db.engine.connect() as conn:
            ev = conn.execute(
                text("SELECT evidence_type FROM case_evidence WHERE assignment_id = :a"),
                {"a": self.aid},
            ).mappings().first()
        self.assertIsNotNone(ev, "case_evidence must survive an rce bridge failure")
        self.assertEqual(ev["evidence_type"], "employment_letter")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
