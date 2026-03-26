"""Wizard draft_json → derivation profile normalization."""
from __future__ import annotations

import unittest

from backend.relocation_plan_draft_normalize import profile_for_plan_derivation
from backend.relocation_plan_status_derivation import (
    RelocationPlanDerivationContext,
    employee_core_profile_satisfied,
    family_details_satisfied,
    route_data_satisfied,
)


class WizardDraftNormalizationTests(unittest.TestCase):
    def test_maps_employee_and_assignment_into_primary_applicant(self) -> None:
        draft = {
            "employeeProfile": {"fullName": "Jordan Patel", "nationality": "United States"},
            "assignmentContext": {"jobTitle": "Product Manager", "seniorityBand": "Mid"},
        }
        prof = profile_for_plan_derivation(draft)
        self.assertTrue(employee_core_profile_satisfied(RelocationPlanDerivationContext(profile=prof)))

    def test_job_level_falls_back_to_salary_band(self) -> None:
        """Wizard step 4 requires salaryBand; seniorityBand is optional."""
        draft = {
            "employeeProfile": {"fullName": "Jordan Patel", "nationality": "United States"},
            "assignmentContext": {
                "jobTitle": "Product Manager",
                "salaryBand": "L6",
            },
        }
        prof = profile_for_plan_derivation(draft)
        self.assertTrue(employee_core_profile_satisfied(RelocationPlanDerivationContext(profile=prof)))

    def test_maps_relocation_basics_to_move_plan(self) -> None:
        draft = {
            "relocationBasics": {
                "originCity": "Oslo",
                "originCountry": "Norway",
                "destCity": "Tokyo",
                "destCountry": "Japan",
            }
        }
        prof = profile_for_plan_derivation(draft)
        self.assertTrue(route_data_satisfied(RelocationPlanDerivationContext(profile=prof)))

    def test_maps_family_members_to_top_level(self) -> None:
        draft = {
            "familyMembers": {
                "maritalStatus": "married",
                "spouse": {"fullName": "Alex Doe"},
                "children": [],
            }
        }
        prof = profile_for_plan_derivation(draft)
        self.assertTrue(family_details_satisfied(RelocationPlanDerivationContext(profile=prof)))

    def test_child_full_name_counts_for_dependents(self) -> None:
        draft = {
            "familyMembers": {
                "maritalStatus": "single",
                "children": [{"fullName": "Sam Child"}],
            }
        }
        prof = profile_for_plan_derivation(draft)
        self.assertTrue(family_details_satisfied(RelocationPlanDerivationContext(profile=prof)))
