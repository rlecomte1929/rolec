"""Unit tests for derived relocation-plan task statuses (pure logic)."""
from __future__ import annotations

import unittest
from datetime import date

from backend.relocation_plan_status_derivation import (
    DerivationThresholds,
    RelocationPlanDerivationContext,
    dependency_block_candidates,
    derive_statuses_for_plan_tasks,
    explicit_status_candidates,
    is_due_soon,
    is_overdue,
    merge_status_candidates,
)
from backend.relocation_plan_task_library import get_task_library_entry_by_code


class MergePrecedenceTests(unittest.TestCase):
    def test_precedence_order(self) -> None:
        self.assertEqual(
            merge_status_candidates(["not_started", "completed", "blocked"]),
            "blocked",
        )
        self.assertEqual(
            merge_status_candidates(["not_started", "in_progress", "completed"]),
            "completed",
        )
        self.assertEqual(
            merge_status_candidates(["not_applicable", "blocked", "completed"]),
            "not_applicable",
        )

    def test_explicit_blocked_beats_completed(self) -> None:
        """Stale manual done loses to derived blocked when both are candidates."""
        cands = explicit_status_candidates("done") + ["blocked"]
        self.assertEqual(merge_status_candidates(cands), "blocked")


class DueHelpersTests(unittest.TestCase):
    def test_overdue(self) -> None:
        self.assertTrue(is_overdue("2020-01-01", today=date(2025, 1, 1)))
        self.assertFalse(is_overdue("2030-01-01", today=date(2025, 1, 1)))
        self.assertFalse(is_overdue(None, today=date(2025, 1, 1)))

    def test_due_soon_threshold(self) -> None:
        today = date(2025, 3, 1)
        self.assertFalse(is_due_soon("2025-03-15", today=today, thresholds=DerivationThresholds(due_soon_days=7)))
        self.assertTrue(is_due_soon("2025-03-08", today=today, thresholds=DerivationThresholds(due_soon_days=7)))
        self.assertTrue(is_due_soon("2025-03-01", today=today, thresholds=DerivationThresholds(due_soon_days=7)))


class RuleAndDependencyTests(unittest.TestCase):
    def _entry(self, code: str):
        e = get_task_library_entry_by_code(code)
        self.assertIsNotNone(e)
        return e

    def test_upload_passport_completed_from_profile_flag(self) -> None:
        ctx = RelocationPlanDerivationContext(
            profile={"complianceDocs": {"hasPassportScans": True}},
        )
        tasks = [(self._entry("upload_passport_copy"), "pending")]
        out = derive_statuses_for_plan_tasks(tasks, ctx)
        self.assertEqual(out["upload_passport_copy"].status, "completed")

    def test_prepare_visa_pack_blocked_without_passport(self) -> None:
        ctx = RelocationPlanDerivationContext(profile={})
        tasks = [(self._entry("prepare_visa_pack"), "pending")]
        out = derive_statuses_for_plan_tasks(tasks, ctx)
        self.assertEqual(out["prepare_visa_pack"].status, "blocked")

    def test_submit_visa_blocked_until_prepare_terminal(self) -> None:
        """Pass-2: dependency not terminal -> blocked (even if explicit says done)."""
        ctx = RelocationPlanDerivationContext(profile={})
        prep = self._entry("prepare_visa_pack")
        sub = self._entry("submit_visa_application")
        tasks = [(prep, "pending"), (sub, "done")]
        out = derive_statuses_for_plan_tasks(tasks, ctx)
        self.assertEqual(out["prepare_visa_pack"].status, "blocked")
        self.assertEqual(out["submit_visa_application"].status, "blocked")

    def test_book_biometrics_not_applicable_when_destination_no_biometrics(self) -> None:
        ctx = RelocationPlanDerivationContext(destination_requires_biometrics=False)
        tasks = [(self._entry("book_biometrics"), "pending")]
        out = derive_statuses_for_plan_tasks(tasks, ctx)
        self.assertEqual(out["book_biometrics"].status, "not_applicable")

    def test_book_biometrics_not_started_when_biometrics_unknown(self) -> None:
        ctx = RelocationPlanDerivationContext(destination_requires_biometrics=None)
        tasks = [(self._entry("book_biometrics"), "pending")]
        out = derive_statuses_for_plan_tasks(tasks, ctx)
        self.assertEqual(out["book_biometrics"].status, "not_started")

    def test_arrange_movers_not_applicable_without_shipment(self) -> None:
        ctx = RelocationPlanDerivationContext(
            move_includes_shipment=False,
            selected_service_keys={"housing"},
        )
        tasks = [(self._entry("arrange_movers"), "pending")]
        out = derive_statuses_for_plan_tasks(tasks, ctx)
        self.assertEqual(out["arrange_movers"].status, "not_applicable")

    def test_confirm_employee_core_profile_completed(self) -> None:
        ctx = RelocationPlanDerivationContext(
            profile={
                "primaryApplicant": {
                    "fullName": "A B",
                    "nationality": "US",
                    "employer": {"jobLevel": "L5", "roleTitle": "Eng"},
                }
            }
        )
        tasks = [(self._entry("confirm_employee_core_profile"), "pending")]
        out = derive_statuses_for_plan_tasks(tasks, ctx)
        self.assertEqual(out["confirm_employee_core_profile"].status, "completed")

    def test_dependency_block_skips_missing_dep_in_slice(self) -> None:
        """Deps not present in the task list do not emit blocked."""
        entry = self._entry("confirm_family_details")
        eff = {"confirm_employee_core_profile": "not_started"}
        self.assertEqual(dependency_block_candidates(entry.task_code, entry, eff), ["blocked"])
        eff2 = {}
        self.assertEqual(dependency_block_candidates(entry.task_code, entry, eff2), [])

    def test_include_debug_populates_trace(self) -> None:
        ctx = RelocationPlanDerivationContext(profile={})
        tasks = [(self._entry("prepare_visa_pack"), "pending")]
        out = derive_statuses_for_plan_tasks(tasks, ctx, include_debug=True)
        r = out["prepare_visa_pack"]
        self.assertIsNotNone(r.debug_trace)
        self.assertIn("pass1_candidates", r.debug_trace or {})


if __name__ == "__main__":
    unittest.main()
