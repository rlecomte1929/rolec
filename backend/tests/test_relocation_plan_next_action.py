"""Tests for relocation plan primary next-action selection."""
from __future__ import annotations

import unittest
from datetime import date

from backend.relocation_plan_next_action import (
    RelocationPlanNextActionResult,
    _selection_pool,
    build_next_action_reason,
    select_next_action_for_relocation_plan,
)
from backend.relocation_plan_service import EnrichedPlanTask, PhasedPlanPhaseBlock
from backend.relocation_plan_status_derivation import DerivationThresholds


def _task(
    task_code: str,
    *,
    phase_key: str = "pre_departure",
    status: str = "not_started",
    owner: str = "employee",
    priority: str = "standard",
    target_date: str | None = None,
    depends_on: tuple[str, ...] = (),
    milestone_type: str | None = None,
) -> EnrichedPlanTask:
    mt = milestone_type or f"mt_{task_code}"
    return EnrichedPlanTask(
        task_id=f"id-{task_code}",
        task_code=task_code,
        milestone_type=mt,
        phase_key=phase_key,
        title=task_code.replace("_", " ").title(),
        short_label=task_code,
        owner=owner,
        priority=priority,
        status=status,
        raw_milestone_status="pending",
        depends_on=depends_on,
        sequence_in_phase=10,
        auto_completion_hint="manual",
        why_this_matters="",
        instructions=(),
        required_inputs=(),
        target_date=target_date,
    )


def _phase(phase_key: str, status: str, tasks: list[EnrichedPlanTask]) -> PhasedPlanPhaseBlock:
    return PhasedPlanPhaseBlock(
        phase_key=phase_key,
        phase_title=phase_key,
        status=status,
        tasks=tasks,
    )


class SelectionPoolTests(unittest.TestCase):
    def test_blocked_excluded_until_all_blocked(self) -> None:
        a = _task("a", status="not_started")
        b = _task("b", status="blocked")
        self.assertEqual({t.task_code for t in _selection_pool([a, b])}, {"a"})
        self.assertEqual({t.task_code for t in _selection_pool([b])}, {"b"})


class OrderingTests(unittest.TestCase):
    def test_active_phase_beats_upcoming(self) -> None:
        upcoming = _task("emp_up", phase_key="logistics", status="not_started", owner="employee")
        active = _task("hr_act", phase_key="pre_departure", status="not_started", owner="hr")
        blocks = [
            _phase("pre_departure", "active", [active]),
            _phase("logistics", "upcoming", [upcoming]),
        ]
        r = select_next_action_for_relocation_plan(blocks, "employee", allow_cross_role_next_action=True)
        self.assertEqual(r.next_action["task_code"], "hr_act")

    def test_critical_before_standard_same_phase(self) -> None:
        std = _task("std", priority="standard", target_date="2020-01-01")
        crit = _task("crit", priority="critical", target_date="2030-01-01")
        blocks = [_phase("pre_departure", "active", [std, crit])]
        r = select_next_action_for_relocation_plan(blocks, "employee")
        self.assertEqual(r.next_action["task_code"], "crit")

    def test_overdue_before_due_soon(self) -> None:
        soon = _task("soon", target_date="2025-03-05")
        late = _task("late", target_date="2025-02-01")
        blocks = [_phase("pre_departure", "active", [soon, late])]
        r = select_next_action_for_relocation_plan(
            blocks, "employee", today=date(2025, 3, 1), allow_cross_role_next_action=True
        )
        self.assertEqual(r.next_action["task_code"], "late")

    def test_employee_owner_beats_hr_same_bucket(self) -> None:
        hr = _task("hr_t", owner="hr")
        emp = _task("emp_t", owner="employee")
        blocks = [_phase("pre_departure", "active", [hr, emp])]
        r = select_next_action_for_relocation_plan(blocks, "employee", allow_cross_role_next_action=True)
        self.assertEqual(r.next_action["task_code"], "emp_t")

    def test_dependencies_satisfied_before_unsatisfied(self) -> None:
        upstream = _task("upstream_gate", status="not_started")
        needs_dep = _task("needs_dep", depends_on=("upstream_gate",))
        no_dep = _task("no_dep", depends_on=())
        blocks = [_phase("pre_departure", "active", [upstream, needs_dep, no_dep])]
        r = select_next_action_for_relocation_plan(blocks, "employee", allow_cross_role_next_action=True)
        self.assertNotEqual(
            r.next_action["task_code"],
            "needs_dep",
            "Tasks with unsatisfied dependencies must sort after satisfied peers",
        )

    def test_in_progress_beats_not_started_tie(self) -> None:
        a = _task("a", status="not_started")
        b = _task("b", status="in_progress")
        blocks = [_phase("pre_departure", "active", [a, b])]
        r = select_next_action_for_relocation_plan(blocks, "employee", allow_cross_role_next_action=True)
        self.assertEqual(r.next_action["task_code"], "b")


class CrossRoleEmptyStateTests(unittest.TestCase):
    def test_employee_sees_null_when_only_hr_open(self) -> None:
        hr_only = _task("hr_review_case_data", owner="hr", milestone_type="task_hr_case_review")
        blocks = [_phase("immigration", "active", [hr_only])]
        r = select_next_action_for_relocation_plan(blocks, "employee")
        self.assertIsNone(r.next_action)
        self.assertEqual(r.empty_state_reason, "Waiting for HR review")

    def test_hr_sees_null_when_only_employee_open(self) -> None:
        emp = _task("upload_passport_copy", owner="employee")
        blocks = [_phase("pre_departure", "active", [emp])]
        r = select_next_action_for_relocation_plan(blocks, "hr")
        self.assertIsNone(r.next_action)
        self.assertEqual(r.empty_state_reason, "Waiting for employee action")

    def test_allow_cross_role_surfaces_other_party(self) -> None:
        hr_only = _task("hr_review_case_data", owner="hr", milestone_type="task_hr_case_review")
        blocks = [_phase("immigration", "active", [hr_only])]
        r = select_next_action_for_relocation_plan(blocks, "employee", allow_cross_role_next_action=True)
        self.assertIsNotNone(r.next_action)
        self.assertEqual(r.next_action["task_code"], "hr_review_case_data")


class ReasonAndCtaTests(unittest.TestCase):
    def test_cta_upload_document(self) -> None:
        t = _task("upload_passport_copy", milestone_type="task_passport_upload")
        blocks = [_phase("pre_departure", "active", [t])]
        r = select_next_action_for_relocation_plan(blocks, "employee", allow_cross_role_next_action=True)
        self.assertEqual(r.next_action["cta_type"], "upload_document")

    def test_reason_due_soon_employee(self) -> None:
        t = _task("upload_passport_copy", target_date="2025-03-05")
        reason = build_next_action_reason(
            t,
            viewer_role="employee",
            downstream_successor_count=0,
            deps_satisfied=True,
            today=date(2025, 3, 1),
            thresholds=DerivationThresholds(due_soon_days=7),
        )
        self.assertEqual(reason, "Due soon and owned by you")

    def test_all_completed_empty_state(self) -> None:
        done = _task("x", status="completed")
        na = _task("y", status="not_applicable")
        blocks = [_phase("pre_departure", "completed", [done, na])]
        r = select_next_action_for_relocation_plan(blocks, "employee")
        self.assertIsNone(r.next_action)
        self.assertEqual(r.empty_state_reason, "No action required right now")


class ResultShapeTests(unittest.TestCase):
    def test_as_dict(self) -> None:
        r = RelocationPlanNextActionResult(next_action=None, empty_state_reason="x")
        self.assertEqual(r.as_dict(), {"next_action": None, "empty_state_reason": "x"})


if __name__ == "__main__":
    unittest.main()
