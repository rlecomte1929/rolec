"""
IMM-18 (AIQ-124) — HR erasure-request processing endpoints.

Exercises the handler functions directly (same approach as
test_imm17_data_export.py — the root conftest mocks backend.database, so the
full FastAPI middleware stack is not viable here).

Covered:
  1. process-erasure-request with bad decision      → 422
  2. process-erasure-request for unknown request    → 404
  3. process-erasure-request already actioned        → 409
  4. approve → anonymises profiles + marks completed
  5. reject  → records decision, anonymises nothing
  6. list_erasure_requests returns rows + pending_count
  7. both HR routes are registered on the router
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from fastapi import HTTPException  # noqa: E402

from backend.app.routers import immigration_gdpr as gdpr  # noqa: E402

HR = {"id": "hr-1", "role": "hr", "email": "hr@example.test"}
ORG = "org-1"


def _result(*, first=None, mappings_first=None, all_rows=None):
    r = MagicMock()
    r.first.return_value = first
    r.mappings.return_value.first.return_value = mappings_first
    r.mappings.return_value.all.return_value = []
    r.all.return_value = all_rows or []
    return r


def _patch_db(execute_results):
    conn = MagicMock()
    conn.execute.side_effect = execute_results
    db = MagicMock()
    db.engine.begin.return_value.__enter__.return_value = conn
    return patch.object(gdpr, "db", db), conn


class TestImm18ErasureProcessing(unittest.TestCase):
    def test_bad_decision_422(self):
        ctx, _ = _patch_db([])
        with ctx:
            with self.assertRaises(HTTPException) as exc:
                gdpr.process_erasure_request(
                    "case-1", gdpr.ProcessErasureBody(request_id="r-1", decision="maybe"), HR, ORG)
        self.assertEqual(exc.exception.status_code, 422)

    def test_unknown_request_404(self):
        ctx, _ = _patch_db([_result(mappings_first=None)])  # request lookup misses
        with ctx:
            with self.assertRaises(HTTPException) as exc:
                gdpr.process_erasure_request(
                    "case-1", gdpr.ProcessErasureBody(request_id="r-x", decision="approve"), HR, ORG)
        self.assertEqual(exc.exception.status_code, 404)

    def test_already_actioned_409(self):
        ctx, _ = _patch_db([_result(mappings_first={"id": "r-1", "status": "completed"})])
        with ctx:
            with self.assertRaises(HTTPException) as exc:
                gdpr.process_erasure_request(
                    "case-1", gdpr.ProcessErasureBody(request_id="r-1", decision="approve"), HR, ORG)
        self.assertEqual(exc.exception.status_code, 409)

    def test_approve_anonymises_and_completes(self):
        ctx, conn = _patch_db([
            _result(mappings_first={"id": "r-1", "status": "pending"}),  # lookup
            _result(all_rows=[("p-1",), ("p-2",)]),                       # profile ids
            _result(),  # fn_anonymise_imm_profile p-1
            _result(),  # fn_anonymise_imm_profile p-2
            _result(),  # UPDATE erasure_requests → completed
            _result(),  # [AIQ-650] insert_audit_log
        ])
        with ctx:
            out = gdpr.process_erasure_request(
                "case-1", gdpr.ProcessErasureBody(request_id="r-1", decision="approve"), HR, ORG)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["profiles_anonymised"], 2)
        self.assertEqual(out["reviewed_by"], "hr-1")
        # lookup + profile-ids + 2 anonymise + 1 update + 1 audit = 6 execute calls
        self.assertEqual(conn.execute.call_count, 6)

    def test_reject_records_only(self):
        ctx, conn = _patch_db([
            _result(mappings_first={"id": "r-1", "status": "pending"}),  # lookup
            _result(),  # UPDATE erasure_requests → rejected
            _result(),  # [AIQ-650] insert_audit_log
        ])
        with ctx:
            out = gdpr.process_erasure_request(
                "case-1",
                gdpr.ProcessErasureBody(request_id="r-1", decision="reject", review_notes="legal hold"),
                HR, ORG)
        self.assertEqual(out["status"], "rejected")
        self.assertEqual(out["profiles_anonymised"], 0)
        # lookup + update + 1 audit — no anonymisation
        self.assertEqual(conn.execute.call_count, 3)

    def test_list_returns_pending_count(self):
        rows = [
            {"id": "r-1", "case_id": "c-1", "employee_id": "e-1", "status": "pending",
             "reason": None, "requested_at": None, "statutory_due_at": None,
             "reviewed_by": None, "reviewed_at": None, "review_notes": None, "completed_at": None},
            {"id": "r-2", "case_id": "c-2", "employee_id": "e-2", "status": "completed",
             "reason": None, "requested_at": None, "statutory_due_at": None,
             "reviewed_by": "hr-1", "reviewed_at": None, "review_notes": None, "completed_at": None},
        ]
        list_result = MagicMock()
        list_result.mappings.return_value.all.return_value = rows
        ctx, _ = _patch_db([list_result])
        with ctx:
            out = gdpr.list_erasure_requests("all", HR, ORG)
        self.assertEqual(len(out["requests"]), 2)
        self.assertEqual(out["pending_count"], 1)

    def test_hr_routes_registered(self):
        paths = {r.path for r in gdpr.router.routes}
        self.assertIn("/api/hr/immigration/erasure-requests", paths)
        self.assertIn("/api/hr/cases/{case_id}/immigration/process-erasure-request", paths)


if __name__ == "__main__":
    unittest.main()
