"""
IMM-17 (AIQ-123) — GDPR right-to-access export + erasure-request endpoints.

Exercises the handler functions directly (the root conftest mocks
backend.database, so going through the full FastAPI middleware stack is not
viable here — same approach as test_b12b_employee_cases.py).

Covered:
  1. /export as a non-owner employee  → 403
  2. /export as the owner             → application/pdf with a non-empty body
  3. /export when over the 24h limit  → 429
  4. /erasure-request as the owner    → 201 dict with request_id + 30-day window
  5. both routes are registered on the router
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from fastapi import HTTPException, Response  # noqa: E402

from backend.app.routers import immigration_gdpr as gdpr  # noqa: E402

EMPLOYEE = {"id": "emp-1", "role": "employee", "email": "e@example.test"}


def _result(*, first=None, scalar=None, mappings_all=None):
    """Build a MagicMock SQLAlchemy Result with the accessors a handler may call."""
    r = MagicMock()
    r.first.return_value = first
    r.scalar.return_value = scalar
    r.mappings.return_value.all.return_value = mappings_all or []
    return r


def _patch_db(execute_results):
    """Patch gdpr.db so engine.begin() yields a conn whose execute() returns each
    queued result in order."""
    conn = MagicMock()
    conn.execute.side_effect = execute_results
    db = MagicMock()
    db.engine.begin.return_value.__enter__.return_value = conn
    return patch.object(gdpr, "db", db), conn


class TestImm17DataExport(unittest.TestCase):
    def test_export_non_owner_403(self):
        ctx, _ = _patch_db([_result(first=None)])  # ownership check fails
        with ctx:
            with self.assertRaises(HTTPException) as exc:
                gdpr.export_my_data("case-x", EMPLOYEE)
        self.assertEqual(exc.exception.status_code, 403)

    def test_export_owner_returns_pdf(self):
        ctx, _ = _patch_db([
            _result(first=(1,)),       # ownership ok
            _result(scalar=0),         # rate-limit count
            _result(mappings_all=[]),  # consent records
            _result(mappings_all=[]),  # access log
        ])
        with ctx, \
             patch.object(gdpr, "_load_profile_for_case_employee",
                          return_value={"id": "p-1", "org_id": "org-1", "full_name": "Jane Doe"}), \
             patch.object(gdpr, "_load_session", return_value={"answers": {"q1": "a1"}}), \
             patch.object(gdpr, "_log_access") as log_access:
            resp = gdpr.export_my_data("case-1", EMPLOYEE)

        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.media_type, "application/pdf")
        self.assertTrue(resp.body.startswith(b"%PDF"))
        self.assertGreater(len(resp.body), 500)
        log_access.assert_called_once()
        self.assertEqual(log_access.call_args.kwargs["action"], "export")

    def test_export_rate_limited_429(self):
        ctx, _ = _patch_db([
            _result(first=(1,)),                          # ownership ok
            _result(scalar=gdpr.MAX_EXPORTS_PER_24H),     # already at limit
        ])
        with ctx, \
             patch.object(gdpr, "_load_profile_for_case_employee", return_value=None):
            with self.assertRaises(HTTPException) as exc:
                gdpr.export_my_data("case-1", EMPLOYEE)
        self.assertEqual(exc.exception.status_code, 429)

    def test_erasure_request_creates_record(self):
        ctx, conn = _patch_db([
            _result(first=(1,)),   # ownership ok
            _result(),             # insert
            _result(),             # [AIQ-650] insert_audit_log
        ])
        with ctx, \
             patch.object(gdpr, "_load_profile_for_case_employee",
                          return_value={"id": "p-1", "org_id": "org-1"}), \
             patch.object(gdpr, "_log_access") as log_access:
            body = gdpr.request_erasure("case-1", gdpr.ErasureRequestBody(reason="leaving"), EMPLOYEE)

        self.assertEqual(body["status"], "pending")
        self.assertIn("request_id", body)
        self.assertEqual(body["response_window_days"], gdpr.ERASURE_RESPONSE_DAYS)
        self.assertIn("statutory_due_at", body)
        log_access.assert_called_once()
        self.assertEqual(log_access.call_args.kwargs["action"], "erasure_request")
        # ownership SELECT + INSERT + audit = 3 execute calls
        self.assertEqual(conn.execute.call_count, 3)

    def test_routes_registered(self):
        paths = {r.path for r in gdpr.router.routes}
        self.assertIn("/api/employee/cases/{case_id}/my-data/export", paths)
        self.assertIn("/api/employee/cases/{case_id}/my-data/erasure-request", paths)


if __name__ == "__main__":
    unittest.main()
