"""
Regression guard — the wired ``interview/status`` handler must resolve all of
its helper names.

``GET /api/employee/cases/{case_id}/interview/status`` is served by
``immigration_status.interview_status`` (AUDIT-B9-imm-6 unwired the original
``immigration.py`` router and registered the 5 modular sub-routers instead).
That handler calls ``_check_consent(...)`` on its first line, but the router
module's ``from ..services.immigration_service import (...)`` block did not
import ``_check_consent``. At request time Python raised
``NameError: name '_check_consent' is not defined`` for *every* call, so the
employee immigration intake page showed "Internal server error" (HTTP 500) for
every case — before the consent check could even run.

The existing suites could not catch this: the non-UUID guard tests exercise the
service functions directly, never through the router, and there was no test that
invoked ``immigration_status.interview_status`` itself.

This guard invokes the handler with the consent query mocked to "no row". With
the import present it degrades to the expected 403 (consent required); without
it the call raises NameError. It is DB-free and deterministic.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from backend.app.routers import immigration_status as router
from backend.app.services import immigration_service as svc


def _patch_db_no_consent():
    """Patch svc.db so the consent SELECT runs and returns no matching row."""
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    db = MagicMock()
    db.engine.begin.return_value.__enter__.return_value = conn
    return patch.object(svc, "db", db)


class TestInterviewStatusImportGuard(unittest.TestCase):
    def test_check_consent_is_resolvable_from_router_namespace(self):
        # The handler references _check_consent at module scope; if it is not
        # imported, the reference is a NameError at call time.
        self.assertTrue(
            hasattr(router, "_check_consent"),
            "immigration_status.py calls _check_consent but does not import it "
            "from immigration_service — every interview/status request 500s "
            "with NameError. Add it to the service import block.",
        )

    def test_interview_status_returns_403_without_consent_not_500(self):
        with _patch_db_no_consent():
            with self.assertRaises(HTTPException) as ctx:
                router.interview_status(
                    case_id="case-1",
                    current_user={"id": "emp-1"},
                )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
