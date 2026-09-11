"""AIQ-2270 — Engine B return phase in the served relocation plan.

A repatriation case through compute_default_milestones + build_phased_plan_from_milestones
must emit a ``return`` block with the expected task_codes and owners. PERMANENT /
domestic_move must not. PHASE_ORDER must contain ``return`` so group_tasks_by_phase
cannot silently drop the block.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.plan_scope import REPATRIATION_PHASES, active_phases_for_case_type
from backend.app.services.relocation_classifier import SUPPRESSED_PHASES, classify_case
from backend.app.services.timeline_service import (
    compute_default_milestones,
    derive_assignment_end_date,
)
from backend.relocation_plan_service import (
    build_phased_plan_from_milestones,
)
from backend.relocation_plan_task_library import (
    PHASE_ORDER,
    RETURN_MILESTONE_TYPES,
    TASK_BY_MILESTONE_TYPE,
)

EXPECTED_RETURN_CODES = (
    "end_of_assignment_review",
    "arrange_return_shipment",
    "host_tax_exit",
    "host_deregistration",
    "home_reregistration",
    "social_security_reentry",
    "lease_deposit_closure",
    "benefits_reinstatement",
    "career_reintegration",
    "return_case_closeout",
)


def _rows(contract_type: str, draft=None):
    return compute_default_milestones(
        case_id="repat-test",
        contract_type=contract_type,
        case_draft=draft,
    )


class TestReturnPhaseOrder(unittest.TestCase):
    def test_return_is_in_phase_order(self) -> None:
        self.assertIn("return", PHASE_ORDER)
        self.assertEqual(PHASE_ORDER[-1], "return")

    def test_group_tasks_by_phase_emits_return_block(self) -> None:
        rows = _rows("repatriation")
        blocks = build_phased_plan_from_milestones(rows)
        keys = [b.phase_key for b in blocks]
        self.assertIn("return", keys)
        self.assertEqual(keys[-1], "return")

    def test_classifier_and_plan_scope_agree(self) -> None:
        from_scope = active_phases_for_case_type("repatriation")
        classified = classify_case({"contract_type": "repatriation"}, [])
        self.assertEqual(from_scope, list(REPATRIATION_PHASES))
        self.assertEqual(classified.active_phases, from_scope)
        self.assertEqual(
            SUPPRESSED_PHASES["repatriation"],
            {"immigration"},
        )
        self.assertIn("return", from_scope)
        self.assertNotIn("immigration", from_scope)


class TestRepatriationPlanView(unittest.TestCase):
    def test_repatriation_has_return_tasks_in_order(self) -> None:
        rows = _rows("repatriation")
        blocks = build_phased_plan_from_milestones(rows)
        ret = next(b for b in blocks if b.phase_key == "return")
        codes = [t.task_code for t in ret.tasks]
        self.assertEqual(set(codes), set(EXPECTED_RETURN_CODES))
        self.assertEqual(codes[0], "end_of_assignment_review")
        self.assertEqual(codes[-1], "return_case_closeout")
        owners = {t.task_code: t.owner for t in ret.tasks}
        self.assertEqual(owners["end_of_assignment_review"], "hr")
        self.assertEqual(owners["host_tax_exit"], "employee")
        self.assertEqual(owners["return_case_closeout"], "hr")
        tax = next(t for t in ret.tasks if t.task_code == "host_tax_exit")
        self.assertEqual(tax.priority, "critical")

    def test_permanent_transfer_has_no_return_phase(self) -> None:
        blocks = build_phased_plan_from_milestones(_rows("permanent_transfer"))
        self.assertFalse(any(b.phase_key == "return" for b in blocks))
        types = {r["milestone_type"] for r in _rows("permanent_transfer")}
        self.assertTrue(types.isdisjoint(RETURN_MILESTONE_TYPES))

    def test_domestic_move_has_no_return_phase(self) -> None:
        blocks = build_phased_plan_from_milestones(_rows("domestic_move"))
        self.assertFalse(any(b.phase_key == "return" for b in blocks))

    def test_lta_does_not_seed_return_at_submit(self) -> None:
        blocks = build_phased_plan_from_milestones(_rows("lta"))
        self.assertFalse(any(b.phase_key == "return" for b in blocks))

    def test_end_date_derivation(self) -> None:
        from datetime import date
        self.assertEqual(
            derive_assignment_end_date(date(2025, 1, 31), 1),
            date(2025, 2, 28),
        )
        self.assertIsNone(derive_assignment_end_date(None, 12))
        self.assertIsNone(derive_assignment_end_date(date(2025, 1, 1), None))

    def test_return_tasks_anchor_on_assignment_end(self) -> None:
        draft = {
            "assignment": {"startDate": "2025-01-01"},
            "assignmentContext": {"expectedDurationMonths": 12},
        }
        rows = _rows("repatriation", draft)
        review = next(r for r in rows if r["milestone_type"] == "task_return_review")
        # end = 2026-01-01; review is 182 days before
        self.assertEqual(review["target_date"], "2025-07-03")

    def test_library_covers_every_return_milestone_type(self) -> None:
        for mt in RETURN_MILESTONE_TYPES:
            self.assertIn(mt, TASK_BY_MILESTONE_TYPE)
            self.assertEqual(TASK_BY_MILESTONE_TYPE[mt].phase_key, "return")


if __name__ == "__main__":
    unittest.main()
