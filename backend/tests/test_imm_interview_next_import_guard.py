"""
Regression guard — the wired ``interview/next`` handler must resolve all of its
helper names.

``GET /api/employee/cases/{case_id}/interview/next`` is served by
``immigration_intake_interview.interview_next`` (AUDIT-B9-imm-6 unwired the
original ``immigration.py`` router and registered the 5 modular sub-routers
instead). That handler calls ``_load_profile_for_case_employee(...)``, but the
router module's ``from ..services.immigration_service import (...)`` block did
not import it. At request time Python raised
``NameError: name '_load_profile_for_case_employee' is not defined`` for *every*
call — after the session row had already been created — so the employee
immigration interview page returned HTTP 500 for every case.

This is the same regression class as #285 (the status router was missing
``_check_consent``); the interview router's ``/next`` handler was missed.

The existing suites could not catch it: the engine tests exercise
``get_next_question`` etc. directly, and the non-UUID guard tests exercise the
service functions directly — neither goes through this router.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from backend.app.routers import immigration_intake_interview as router
from backend.app.services import immigration_service as svc


def _patch_svc_db_no_row():
    """Patch svc.db so the profile SELECT runs and returns no matching row."""
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    db = MagicMock()
    db.engine.begin.return_value.__enter__.return_value = conn
    return patch.object(svc, "db", db)


class TestInterviewNextImportGuard(unittest.TestCase):
    def test_load_profile_is_resolvable_from_router_namespace(self):
        # interview_next references _load_profile_for_case_employee at module
        # scope; if it is not imported, the reference is a NameError at call time.
        self.assertTrue(
            hasattr(router, "_load_profile_for_case_employee"),
            "immigration_intake_interview.py calls _load_profile_for_case_employee "
            "but does not import it from immigration_service — every "
            "interview/next request 500s with NameError. Add it to the service "
            "import block.",
        )

    def test_interview_next_returns_payload_not_nameerror(self):
        # Patch the two earlier helpers (consent passes, session loads) so the
        # handler reaches the _load_profile_for_case_employee call. With the
        # import present it resolves and the handler returns a payload; without
        # it the call raises NameError.
        session = {"id": "sess-1", "prefilled_fields": [], "answers": {}}
        with patch.object(router, "_check_consent", return_value=True), \
                patch.object(router, "_load_or_create_session", return_value=session), \
                _patch_svc_db_no_row():
            result = router.interview_next(
                case_id="case-1",
                current_user={"id": "emp-1", "org_id": ""},
            )
        self.assertEqual(result["session_id"], "sess-1")
        self.assertIn("next_question", result)
        self.assertIn("is_complete", result)


if __name__ == "__main__":
    unittest.main()
