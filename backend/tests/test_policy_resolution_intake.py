"""Case wizard draft (profile_json) merged into policy resolution context."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_resolution import extract_resolution_context


class PolicyResolutionIntakeTests(unittest.TestCase):
    def test_case_draft_contract_type_and_children(self) -> None:
        draft = {
            "relocationBasics": {"durationMonths": 24, "destCountry": "DE", "destCity": "Berlin"},
            "familyMembers": {
                "maritalStatus": "married",
                "children": [{"fullName": "Kid", "age": 8}],
            },
            "assignmentContext": {"contractType": "permanent", "jobTitle": "Engineer"},
        }
        ctx = extract_resolution_context({}, None, draft, {})
        self.assertEqual(ctx["assignment_type"], "PERMANENT")
        self.assertEqual(ctx["family_status"], "with_children")
        self.assertEqual(ctx["children_count"], 1)
        self.assertEqual(ctx["duration_months"], 24)

    def test_employee_profile_wins_over_draft(self) -> None:
        draft = {
            "relocationBasics": {},
            "familyMembers": {"maritalStatus": "single"},
            "assignmentContext": {"contractType": "permanent"},
        }
        emp = {"maritalStatus": "married", "spouse": {"fullName": "Partner"}}
        ctx = extract_resolution_context({}, None, draft, emp)
        self.assertEqual(ctx["has_spouse"], True)
        self.assertEqual(ctx["family_status"], "married")


if __name__ == "__main__":
    unittest.main()
