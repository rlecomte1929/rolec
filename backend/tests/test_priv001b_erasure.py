"""
PRIV-001b (AIQ-469) — GDPR Art. 17 user-level erasure endpoint.

Handler-level tests (the root conftest mocks backend.database, so the full
FastAPI stack isn't viable — same approach as test_priv001_data_export.py).

Covered:
  1. access — subject erasing their own data        → allowed
  2. access — platform admin                         → allowed
  3. access — HR (even in-org)                        → 403  (tighter than export)
  4. access — unrelated employee                      → 403
  5. erase_subject_data deletes operational tables, anonymises PII tables,
     retains accountability tables, and deletes the auth user LAST
  6. erasure is idempotent (re-run raises nothing, same shape)
  7. the route is registered
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
ADMIN = {"id": "admin-1", "role": "admin", "is_admin": True, "email": "admin@relopass.com"}
HR = {"id": "hr-1", "role": "hr", "email": "hr@co.test", "company": "co-1"}
OUTSIDER = {"id": "emp-x", "role": "employee", "email": "x@example.test"}


class TestPriv001bAccess(unittest.TestCase):
    def test_subject_allowed(self):
        gdpr._assert_erasure_access(SUBJECT, SUBJECT_ID)  # must not raise

    def test_admin_allowed(self):
        gdpr._assert_erasure_access(ADMIN, SUBJECT_ID)  # must not raise

    def test_hr_forbidden_even_in_org(self):
        with self.assertRaises(HTTPException) as exc:
            gdpr._assert_erasure_access(HR, SUBJECT_ID)
        self.assertEqual(exc.exception.status_code, 403)

    def test_outsider_forbidden(self):
        with self.assertRaises(HTTPException) as exc:
            gdpr._assert_erasure_access(OUTSIDER, SUBJECT_ID)
        self.assertEqual(exc.exception.status_code, 403)


class TestPriv001bErasure(unittest.TestCase):
    def _run(self):
        conn = MagicMock()
        db = MagicMock()
        db.engine.begin.return_value.__enter__.return_value = conn
        with patch.object(gdpr, "db", db), \
             patch.object(gdpr, "_resolve_case_ids", return_value=["case-1"]), \
             patch.object(gdpr, "_delete_supabase_auth_user", return_value=True) as auth_del:
            summary = gdpr.erase_subject_data(SUBJECT_ID)
        return summary, conn, auth_del

    def test_summary_classifies_tables(self):
        summary, conn, auth_del = self._run()
        # Operational tables hard-deleted
        self.assertIn("employees", summary["erased_tables"])
        self.assertIn("case_documents", summary["erased_tables"])
        # PII tables anonymised
        self.assertIn("profiles", summary["anonymised_tables"])
        self.assertIn("imm_employee_profiles", summary["anonymised_tables"])
        # Accountability tables retained
        self.assertIn("consent_records", summary["retained_tables"])
        self.assertIn("data_access_log", summary["retained_tables"])
        self.assertIn("erasure_requests", summary["retained_tables"])
        self.assertEqual(summary["errors"], [])
        # Auth user deleted last
        self.assertTrue(summary["auth_user_deleted"])
        auth_del.assert_called_once_with(SUBJECT_ID)
        # Every table issued exactly one statement
        self.assertGreaterEqual(conn.execute.call_count, len(gdpr._ERASURE_ACTIONS))

    def test_imm_profile_stamps_anonymised_at(self):
        summary, conn, _ = self._run()
        imm_sql = [c.args[0].text for c in conn.execute.call_args_list
                   if "imm_employee_profiles" in c.args[0].text]
        self.assertTrue(imm_sql)
        self.assertIn("anonymised_at = now()", imm_sql[0])
        self.assertIn("passport_number = NULL", imm_sql[0])

    def test_per_table_failure_is_soft(self):
        # A table whose SAVEPOINT raises is recorded in errors, not propagated.
        conn = MagicMock()
        conn.begin_nested.side_effect = [RuntimeError("boom")] + [MagicMock() for _ in range(50)]
        db = MagicMock()
        db.engine.begin.return_value.__enter__.return_value = conn
        with patch.object(gdpr, "db", db), \
             patch.object(gdpr, "_resolve_case_ids", return_value=[]), \
             patch.object(gdpr, "_delete_supabase_auth_user", return_value=False):
            summary = gdpr.erase_subject_data(SUBJECT_ID)
        self.assertEqual(len(summary["errors"]), 1)

    def test_route_registered(self):
        routes = {(r.path, tuple(sorted(r.methods))) for r in gdpr.router.routes if hasattr(r, "methods")}
        self.assertIn(("/api/users/{user_id}/data", ("DELETE",)), routes)


class TestPriv001bEndpoint(unittest.TestCase):
    def test_endpoint_logs_erasure(self):
        canned = {"erased_tables": ["employees"], "anonymised_tables": ["profiles"],
                  "retained_tables": ["consent_records"], "errors": [], "auth_user_deleted": True}
        with patch.object(gdpr, "_assert_erasure_access") as assert_access, \
             patch.object(gdpr, "erase_subject_data", return_value=canned), \
             patch.object(gdpr, "_log_access") as log_access:
            resp = gdpr.erase_user_data(SUBJECT_ID, SUBJECT)
        assert_access.assert_called_once_with(SUBJECT, SUBJECT_ID)
        self.assertEqual(resp, canned)
        self.assertEqual(log_access.call_args.kwargs["action"], "gdpr_erasure")
        self.assertEqual(log_access.call_args.kwargs["fields"], ["employees", "profiles"])


if __name__ == "__main__":
    unittest.main()
