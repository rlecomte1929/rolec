"""
Regression: GET /api/relocation-plans/{case_id}/view 500 for freshly-accepted /
empty-intake cases.

Root cause was a broken relative import inside load_profile_draft_for_case
(`from ..app import crud` → backend.app.app.crud, which does not exist →
ModuleNotFoundError on every plan-view request). These tests lock in:

  1. load_profile_draft_for_case imports the correct crud module and does not
     raise ModuleNotFoundError (the actual bug).
  2. build_relocation_plan_view_response assembles a valid, empty plan for a case
     with no milestones and no intake draft (graceful empty-intake contract — the
     state every employee is in immediately after accepting a case).

Pure unittest — no live server, DB calls mocked.
"""
from __future__ import annotations

import unittest
from unittest import mock

from backend.app.services import relocation_plan_view_service as svc
from backend.relocation_plan_view_schemas import RelocationPlanViewResponse


class TestLoadProfileDraftImport(unittest.TestCase):
    def test_no_module_not_found_error(self):
        """The function must resolve backend.app.crud, not backend.app.app.crud."""
        # crud.get_case is patched to None so we exercise the import path without a DB.
        with mock.patch("backend.app.crud.get_case", return_value=None):
            result = svc.load_profile_draft_for_case(session=mock.MagicMock(), case_id="case-x")
        self.assertEqual(result, {})  # missing case → empty draft, no exception

    def test_parses_draft_json(self):
        fake_case = mock.MagicMock()
        fake_case.draft_json = '{"familyMembers": {"maritalStatus": "Single"}}'
        with mock.patch("backend.app.crud.get_case", return_value=fake_case):
            result = svc.load_profile_draft_for_case(session=mock.MagicMock(), case_id="case-x")
        self.assertEqual(result["familyMembers"]["maritalStatus"], "Single")

    def test_malformed_draft_json_returns_empty(self):
        fake_case = mock.MagicMock()
        fake_case.draft_json = "not json{"
        with mock.patch("backend.app.crud.get_case", return_value=fake_case):
            result = svc.load_profile_draft_for_case(session=mock.MagicMock(), case_id="case-x")
        self.assertEqual(result, {})


class TestEmptyIntakePlanView(unittest.TestCase):
    def test_empty_milestones_and_draft_builds_valid_response(self):
        """No milestones + no intake draft → a valid, empty plan (not a crash)."""
        resp = svc.build_relocation_plan_view_response(
            case_id="case-empty",
            assignment_id=None,            # no assignment_id → list_case_services skipped
            milestones=[],
            profile_draft={},
            mobility_case_id=None,         # → _mobility_documents_and_evals returns empties, db untouched
            db=mock.MagicMock(),
            viewer_role="employee",
            debug=False,
            request_id="test-empty",
        )
        self.assertIsInstance(resp, RelocationPlanViewResponse)
        self.assertEqual(resp.case_id, "case-empty")
        self.assertEqual(resp.phases, [])          # empty content arrays, never null
        self.assertIsNone(resp.next_action)         # nothing to do yet
        self.assertIsNotNone(resp.summary)          # summary object present


if __name__ == "__main__":
    unittest.main(verbosity=2)
