"""Tests for phased relocation plan engine (task library + adapter)."""
from __future__ import annotations

import unittest

from backend.relocation_plan_service import (
    RelocationPlanPhaseEngine,
    adapt_milestone_row,
    build_phased_plan_from_milestones,
    map_milestone_status_to_plan_status,
)
from backend.relocation_plan_task_library import (
    PHASE_ORDER,
    TASK_BY_MILESTONE_TYPE,
    iter_task_library,
    phase_index,
)


class RelocationPlanLibraryTests(unittest.TestCase):
    def test_all_mvp_codes_mapped_from_milestone_types(self) -> None:
        # Core MVP codes (original set)
        expected_core = {
            "task_profile_core",
            "task_family_dependents",
            "task_passport_upload",
            "task_employment_letter",
            "task_route_verify",
            "task_hr_case_review",
            "task_immigration_review",
            "task_visa_docs_prep",
            "task_visa_submit",
            "task_biometrics",
            "task_temp_housing",
            "task_movers_shipment",
            "task_provider_coordination",
            "task_travel_plan",
            "task_arrival_registration",
            "task_tax_local_registration",
            "task_settling_in",
        }
        # Extended codes: family, EU, L1B, Japan, UK Skilled Worker (added in S4/P2/P5)
        expected_extended = {
            "task_dependent_visa",
            "task_partner_family_visa",
            "task_partner_mvv",
            "task_spouse_work_permit",
            "task_school_research",
            "task_school_application",
            "task_eu_registration",
            "task_l1b_support_letter",
            "task_l1b_petition_prep",
            "task_l1b_petition_filing",
            "task_l1b_visa_interview",
            "task_l1b_port_of_entry",
            "task_l1b_ssn",
            "task_japan_coe_prep",
            "task_japan_coe_visa",
            "task_japan_municipal_reg",
            "task_japan_residence_card",
            "task_uk_cos_request",
            "task_uk_visa_application",
            "task_uk_biometric_appointment",
            "task_uk_brp_collection",
            "task_uk_right_to_work_check",
            "task_return_review",
            "task_return_shipment",
            "task_return_host_tax",
            "task_return_host_dereg",
            "task_return_home_reg",
            "task_return_social",
            "task_return_lease",
            "task_return_benefits",
            "task_return_career",
            "task_return_closeout",
        }
        expected = expected_core | expected_extended
        actual = set(TASK_BY_MILESTONE_TYPE.keys())
        # All expected codes must be present
        self.assertTrue(
            expected.issubset(actual),
            f"Missing from library: {expected - actual}",
        )
        # No unknown codes should exist either
        self.assertEqual(actual, expected, f"Unexpected codes: {actual - expected}")

    def test_phase_order_covers_all_library_phases(self) -> None:
        phases = {t.phase_key for t in iter_task_library()}
        for p in phases:
            self.assertIn(p, PHASE_ORDER)
        self.assertTrue(all(phase_index(p) < 99 for p in phases))


class RelocationPlanServiceTests(unittest.TestCase):
    def test_map_status(self) -> None:
        self.assertEqual(map_milestone_status_to_plan_status("pending"), "not_started")
        self.assertEqual(map_milestone_status_to_plan_status("done"), "completed")
        self.assertEqual(map_milestone_status_to_plan_status("skipped"), "completed")
        self.assertEqual(map_milestone_status_to_plan_status("blocked"), "blocked")
        self.assertEqual(map_milestone_status_to_plan_status("in_progress"), "in_progress")

    def test_adapt_enriches_from_library(self) -> None:
        row = {
            "id": "m1",
            "milestone_type": "task_passport_upload",
            "title": "",
            "status": "pending",
            "owner": "employee",
            "criticality": "critical",
        }
        t = adapt_milestone_row(row)
        self.assertEqual(t.task_code, "upload_passport_copy")
        self.assertEqual(t.phase_key, "pre_departure")
        self.assertEqual(t.status, "not_started")
        self.assertTrue(t.why_this_matters)

    def test_topo_core_before_passport(self) -> None:
        rows = [
            {
                "id": "p",
                "milestone_type": "task_passport_upload",
                "title": "P",
                "status": "pending",
                "owner": "employee",
                "criticality": "critical",
            },
            {
                "id": "c",
                "milestone_type": "task_profile_core",
                "title": "C",
                "status": "pending",
                "owner": "employee",
                "criticality": "normal",
            },
        ]
        eng = RelocationPlanPhaseEngine()
        ordered = eng.enrich_only(rows)
        codes = [x.task_code for x in ordered]
        self.assertEqual(codes[0], "confirm_employee_core_profile")
        self.assertEqual(codes[1], "upload_passport_copy")

    def test_build_phased_plan(self) -> None:
        rows = [
            {
                "id": "1",
                "milestone_type": "task_profile_core",
                "title": "T",
                "status": "done",
                "owner": "employee",
                "criticality": "normal",
            },
            {
                "id": "2",
                "milestone_type": "task_passport_upload",
                "title": "T",
                "status": "pending",
                "owner": "employee",
                "criticality": "critical",
            },
        ]
        blocks = build_phased_plan_from_milestones(rows)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].phase_key, "pre_departure")
        self.assertEqual(blocks[0].status, "active")
        self.assertEqual(blocks[0].task_counts["completed"], 1)

    def test_unknown_milestone_fallback(self) -> None:
        row = {
            "id": "x",
            "milestone_type": "custom_vendor_task",
            "title": "Custom",
            "status": "pending",
            "owner": "hr",
            "criticality": "normal",
        }
        t = adapt_milestone_row(row)
        self.assertEqual(t.task_code, "custom_vendor_task")
        self.assertEqual(t.phase_key, "pre_departure")


if __name__ == "__main__":
    unittest.main()
