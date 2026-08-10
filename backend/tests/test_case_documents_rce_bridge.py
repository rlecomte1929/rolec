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

This module deliberately has **no import-time side effects**. The SQLite harness is
reused from ``test_case_documents_flow`` (rather than copied), but imported inside
``setUp`` rather than at module scope: that module pops ``backend.database`` from
sys.modules in its body to get the real Database back past the root conftest's
MagicMock, and pulling it in during collection re-runs that pop at the wrong moment.
The symptom was four unrelated ``test_catalog_promotion`` tests reading the wrong
engine in a full-suite run while every isolated and pairwise run stayed green —
measured by deselecting every test in this file and watching them fail anyway, which
is what pinned it to import time rather than anything these tests do.
"""
from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock, patch

_USER = {"id": "emp-1", "role": "EMPLOYEE", "email": "docflow@example.com"}


class CaseDocumentRceBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        import backend.app.routers.case_documents as cdoc

        # Imported HERE, not at module scope. test_case_documents_flow pops
        # backend.database from sys.modules in its module body to get the real
        # Database back; pulling it in at collection time re-runs that pop at the
        # wrong moment and leaves a second backend.database instance behind, which
        # silently redirected four unrelated test_catalog_promotion tests to the
        # wrong engine in a full-suite run while every isolated run stayed green.
        # Deferring to setUp keeps this module free of import-time side effects.
        from .test_case_documents_flow import (
            _fresh_db,
            _make_app,
            _mobility_case_id,
            _seed_graph,
        )

        self._make_app, self._mobility_case_id = _make_app, _mobility_case_id
        self.cdoc = cdoc
        # _fresh_db reassigns the process-global dbmod._engine / _is_sqlite. Leaving
        # them pointed at this test's in-memory engine redirects every later module in
        # a full-suite run to the wrong database.
        import backend.database as dbmod

        self._dbmod = dbmod
        self._prev_engine = getattr(dbmod, "_engine", None)
        self._prev_is_sqlite = getattr(dbmod, "_is_sqlite", None)
        self.db = _fresh_db()
        self._prev_main_db = cdoc.main_db
        cdoc.main_db = self.db
        self._prev_access = cdoc._assert_case_access
        cdoc._assert_case_access = lambda user, case_id: None
        self.client = TestClient(self._make_app(cdoc), raise_server_exceptions=False)

        self.aid, self.case_id, _hr, _emp = _seed_graph(self.db)
        self.mobility_id = self._mobility_case_id(self.db, self.aid)
        # The whole point of the id assertions below: these must be different values.
        self.assertNotEqual(self.case_id, self.mobility_id)

    def tearDown(self) -> None:
        self.cdoc.main_db = self._prev_main_db
        self.cdoc._assert_case_access = self._prev_access
        self._dbmod._engine = self._prev_engine
        self._dbmod._is_sqlite = self._prev_is_sqlite

    def _fake_supabase(self):
        sb = MagicMock()
        sb.storage.from_.return_value.upload.return_value = None
        return sb

    def _upload(self, bridge_mock, pipeline_mock=None):
        """POST a PDF with the bridge (and the pipeline worker) patched."""
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
        ever regresses the upload must still succeed — by this point the file is in
        storage and case_evidence is committed, so a 500 would report failure for an
        upload that worked and invite a duplicate retry."""
        from sqlalchemy import text

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
