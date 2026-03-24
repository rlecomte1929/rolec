"""Tests for canonical relocation plan view assembly."""
from __future__ import annotations

import unittest

from backend.relocation_plan_view_schemas import RelocationPlanViewRole
from backend.services.relocation_plan_view_service import build_relocation_plan_view_response
from backend.database import db


class RelocationPlanViewAssemblyTests(unittest.TestCase):
    def test_empty_milestones_returns_zero_summary(self) -> None:
        out = build_relocation_plan_view_response(
            case_id="case-1",
            assignment_id=None,
            milestones=[],
            profile_draft={},
            mobility_case_id=None,
            db=db,
            viewer_role="employee",
            debug=False,
            request_id="test-req",
        )
        self.assertEqual(out.case_id, "case-1")
        self.assertEqual(out.summary.total_tasks, 0)
        self.assertEqual(out.summary.completion_ratio, 0.0)
        self.assertEqual(out.role, RelocationPlanViewRole.EMPLOYEE)
        self.assertIsNone(out.next_action)
        self.assertEqual(out.empty_state_reason, "No action required right now")
        self.assertIsNone(out.debug)

    def test_debug_payload_when_requested(self) -> None:
        out = build_relocation_plan_view_response(
            case_id="case-1",
            assignment_id=None,
            milestones=[],
            profile_draft={},
            mobility_case_id=None,
            db=db,
            viewer_role="hr",
            debug=True,
            request_id="test-req",
        )
        self.assertIsNotNone(out.debug)
        assert out.debug is not None
        self.assertIn("document_row_count", out.debug)


if __name__ == "__main__":
    unittest.main()
