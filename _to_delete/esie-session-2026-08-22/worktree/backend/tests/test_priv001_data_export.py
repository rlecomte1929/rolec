"""
PRIV-001 (AIQ-469) — GDPR Art. 20 user-level data-export endpoint.

Exercises the handler + access-control helpers directly (the root conftest mocks
backend.database, so the full FastAPI middleware stack isn't viable here — same
approach as test_imm17_data_export.py).

Covered:
  1. access — the subject exporting their own data         → allowed
  2. access — a platform admin exporting any subject        → allowed
  3. access — an HR admin in the subject's org              → allowed
  4. access — an HR admin in a DIFFERENT org                → 403
  5. access — an unrelated employee                         → 403
  6. build_subject_export assembles {user_id, exported_at, tables}
  7. export_user_data returns the export and logs the access (fail-soft)
  8. the route is registered on the router
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from fastapi import HTTPException  # noqa: E402

from backend.app.routers import gdpr  # noqa: E402

SUBJECT_ID = "11111111-1111-1111-1111-111111111111"
SUBJECT = {"id": SUBJECT_ID, "role": "employee", "email": "subject@example.test"}
ADMIN = {"id": "admin-1", "role": "admin", "email": "admin@relopass.com"}
HR_SAME = {"id": "hr-same", "role": "hr", "email": "hr@co.test", "company": "co-1"}
HR_OTHER = {"id": "hr-other", "role": "hr", "email": "hr@other.test", "company": "co-2"}
OUTSIDER = {"id": "emp-x", "role": "employee", "email": "x@example.test"}


def _db_with_company(hr_company):
    db = MagicMock()
    db.get_hr_company_id.return_value = hr_company
    return db


class TestPriv001Access(unittest.TestCase):
    def test_subject_exports_own_data(self):
        # No db access needed for the own-data short-circuit.
        gdpr._assert_export_access(SUBJECT, SUBJECT_ID)  # must not raise

    def test_platform_admin_allowed(self):
        gdpr._assert_export_access(ADMIN, SUBJECT_ID)  # must not raise

    def test_hr_in_subject_org_allowed(self):
        with patch.object(gdpr, "db", _db_with_company("co-1")), \
             patch.object(gdpr, "_subject_company_ids", return_value={"co-1"}):
            gdpr._assert_export_access(HR_SAME, SUBJECT_ID)  # must not raise

    def test_hr_cross_org_forbidden(self):
        with patch.object(gdpr, "db", _db_with_company("co-2")), \
             patch.object(gdpr, "_subject_company_ids", return_value={"co-1"}):
            with self.assertRaises(HTTPException) as exc:
                gdpr._assert_export_access(HR_OTHER, SUBJECT_ID)
        self.assertEqual(exc.exception.status_code, 403)

    def test_unrelated_employee_forbidden(self):
        with patch.object(gdpr, "db", _db_with_company(None)):
            with self.assertRaises(HTTPException) as exc:
                gdpr._assert_export_access(OUTSIDER, SUBJECT_ID)
        self.assertEqual(exc.exception.status_code, 403)


class TestPriv001Export(unittest.TestCase):
    def test_build_subject_export_shape(self):
        db = MagicMock()
        db.engine.begin.return_value.__enter__.return_value = MagicMock()
        with patch.object(gdpr, "db", db), \
             patch.object(gdpr, "_resolve_case_ids", return_value=["case-1"]), \
             patch.object(gdpr, "_rows", side_effect=lambda conn, t, w, p:
                          [{"id": 1}] if t in ("profiles", "case_documents") else []):
            export = gdpr.build_subject_export(SUBJECT_ID)

        self.assertEqual(export["user_id"], SUBJECT_ID)
        self.assertIn("exported_at", export)
        # Only the non-empty tables are included.
        self.assertEqual(set(export["tables"]), {"profiles", "case_documents"})

    def test_export_user_data_logs_access(self):
        canned = {"user_id": SUBJECT_ID, "exported_at": "now", "tables": {"profiles": [{"id": 1}]}}
        with patch.object(gdpr, "_assert_export_access") as assert_access, \
             patch.object(gdpr, "build_subject_export", return_value=canned), \
             patch.object(gdpr, "_log_access") as log_access:
            resp = gdpr.export_user_data(SUBJECT_ID, SUBJECT)

        assert_access.assert_called_once_with(SUBJECT, SUBJECT_ID)
        self.assertEqual(resp, canned)
        log_access.assert_called_once()
        self.assertEqual(log_access.call_args.kwargs["action"], "gdpr_data_export")
        self.assertEqual(log_access.call_args.kwargs["fields"], ["profiles"])

    def test_route_registered(self):
        paths = {r.path for r in gdpr.router.routes}
        self.assertIn("/api/users/{user_id}/data-export", paths)


if __name__ == "__main__":
    unittest.main()
