"""
IMM-19 (AIQ-125) — employee consent listing + withdrawal endpoints.

Exercises the handler functions directly (the root conftest mocks
backend.database, so going through the full FastAPI middleware stack is not
viable here — same approach as test_imm17_data_export.py).

Covered:
  1. /consent list returns latest record per purpose with derived `active` flag
  2. /consent/withdraw on an active purpose  → withdrawn dict, audit logged
  3. /consent/withdraw with no active consent → 404
  4. both new routes are registered on the router
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from fastapi import HTTPException  # noqa: E402

from backend.app.routers import immigration_intake_consent as consent  # noqa: E402

EMPLOYEE = {"id": "emp-1", "role": "employee", "email": "e@example.test"}


def _result(*, mappings_all=None, mappings_first=None, rowcount=0):
    """Build a MagicMock SQLAlchemy Result with the accessors a handler may call."""
    r = MagicMock()
    r.mappings.return_value.all.return_value = mappings_all or []
    r.mappings.return_value.first.return_value = mappings_first
    r.rowcount = rowcount
    return r


#: The ledger row `withdraw_consent_employee` reads to decide whether consent is held.
#: Mirrors the real columns it selects — `consent_version`/`consent_text_hash` are carried
#: onto the withdrawal row, and both are NOT NULL in Postgres.
_HELD = {
    "consented": True,
    "withdrawn_at": None,
    "consent_version": "v1",
    "consent_text_hash": "hash-v1",
}


def _patch_db(execute_results):
    """Patch consent.db so engine.begin() yields a conn whose execute() returns
    each queued result in order."""
    conn = MagicMock()
    conn.execute.side_effect = execute_results
    db = MagicMock()
    db.engine.begin.return_value.__enter__.return_value = conn
    return patch.object(consent, "db", db), conn


class TestImm19ConsentManagement(unittest.TestCase):
    def test_list_derives_active_flag(self):
        rows = [
            {"purpose": "immigration_processing", "consented": True,
             "withdrawn_at": None, "withdrawn_reason": None},
            {"purpose": "vendor_sharing", "consented": False,
             "withdrawn_at": "2026-06-01T00:00:00Z", "withdrawn_reason": "no thanks"},
        ]
        ctx, _ = _patch_db([_result(mappings_all=rows)])
        with ctx:
            out = consent.list_consent_employee("case-1", EMPLOYEE)

        by_purpose = {r["purpose"]: r for r in out["consent_records"]}
        self.assertTrue(by_purpose["immigration_processing"]["active"])
        self.assertFalse(by_purpose["vendor_sharing"]["active"])

    def test_withdraw_active_consent(self):
        # Two statements now: read the latest ledger row, then APPEND a withdrawal row.
        ctx, conn = _patch_db([_result(mappings_first=_HELD), _result(rowcount=1)])
        with ctx, patch.object(consent, "_log_access") as log_access, \
                patch.object(consent, "insert_audit_log"):
            out = consent.withdraw_consent_employee(
                "case-1", consent.WithdrawConsentBody(purpose="vendor_sharing"), EMPLOYEE
            )

        self.assertTrue(out["withdrawn"])
        self.assertEqual(out["purpose"], "vendor_sharing")
        self.assertEqual(out["records_withdrawn"], 1)
        log_access.assert_called_once()
        self.assertEqual(log_access.call_args.kwargs["action"], "consent_withdraw")

    def test_withdraw_appends_and_never_updates(self):
        """AIQ-1803. `consent_records` is append-only — a trigger blocks UPDATE and DELETE
        for every role. This endpoint used to issue an UPDATE, so it raised for every
        caller and withdrawal was impossible in production. Pin the statement shape here:
        this mocked lane cannot see the trigger, which is exactly how the bug survived.
        The behavioural proof lives in
        `backend/tests/integration/test_consent_withdrawal.py`.
        """
        ctx, conn = _patch_db([_result(mappings_first=_HELD), _result(rowcount=1)])
        with ctx, patch.object(consent, "_log_access"), \
                patch.object(consent, "insert_audit_log"):
            consent.withdraw_consent_employee(
                "case-1", consent.WithdrawConsentBody(purpose="vendor_sharing"), EMPLOYEE
            )

        statements = " ".join(
            str(call.args[0]).upper() for call in conn.execute.call_args_list
        )
        self.assertIn("INSERT INTO PUBLIC.CONSENT_RECORDS", statements)
        self.assertNotIn("UPDATE PUBLIC.CONSENT_RECORDS", statements)

    def test_withdraw_no_active_consent_404(self):
        ctx, _ = _patch_db([_result(mappings_first=None)])
        with ctx, patch.object(consent, "_log_access"):
            with self.assertRaises(HTTPException) as exc:
                consent.withdraw_consent_employee(
                    "case-1", consent.WithdrawConsentBody(purpose="vendor_sharing"), EMPLOYEE
                )
        self.assertEqual(exc.exception.status_code, 404)

    def test_withdraw_already_withdrawn_404(self):
        """The latest row says withdrawn, so there is nothing to withdraw — and no second
        withdrawal row is appended."""
        withdrawn = dict(_HELD, consented=False, withdrawn_at="2026-06-01T00:00:00Z")
        ctx, conn = _patch_db([_result(mappings_first=withdrawn)])
        with ctx, patch.object(consent, "_log_access"):
            with self.assertRaises(HTTPException) as exc:
                consent.withdraw_consent_employee(
                    "case-1", consent.WithdrawConsentBody(purpose="vendor_sharing"), EMPLOYEE
                )
        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(conn.execute.call_count, 1, "must not append on a no-op withdrawal")

    def test_routes_registered(self):
        paths = {(r.path, tuple(sorted(r.methods))) for r in consent.router.routes}
        self.assertIn(("/api/employee/cases/{case_id}/consent", ("GET",)), paths)
        self.assertIn(("/api/employee/cases/{case_id}/consent/withdraw", ("POST",)), paths)


if __name__ == "__main__":
    unittest.main()
