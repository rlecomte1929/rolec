"""
[Persist AI roadmap] After a successful generation, the AI steps are written
into case_milestones (replacing the deterministic seed) so the relocation plan
view — and the employee roadmap page (AIQ-1005) — serves corridor-specific
content. These tests pin the pure step→milestone mapping and the persist
helper's replace + no-op behaviour (DB mocked).
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("POLICY_ASSISTANT_LLM", "mock")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.case_roadmap_profile import (  # noqa: E402
    map_generated_steps_to_milestones,
    persist_generated_milestones,
)

_STEPS = [
    {
        "order": 1,
        "title": "Verify qualification via Anabin",
        "description": "Check the German Anabin database for H+ status.",
        "source_url": "https://anabin.kmk.org",
        "confidence": "high",
        "requires_expert_review": False,
        "phase": "immigration",
    },
    {
        "order": 2,
        "title": "Submit EU Blue Card application (Type D visa)",
        "description": None,
        "confidence": "high",
        "requires_expert_review": True,
        # no phase → defaults to pre_departure
    },
    {"order": 3, "title": "   ", "description": "blank title — dropped"},
]


class MapGeneratedStepsTests(unittest.TestCase):
    def test_maps_steps_to_milestone_kwargs(self):
        rows = map_generated_steps_to_milestones(_STEPS, "IN→DE")
        # The blank-title step is dropped.
        self.assertEqual(len(rows), 2)
        # milestone_type encodes the phase so the plan service buckets it.
        self.assertEqual(rows[0]["milestone_type"], "immigration_ai_01")
        self.assertEqual(rows[0]["title"], "Verify qualification via Anabin")
        self.assertEqual(rows[0]["description"], "Check the German Anabin database for H+ status.")
        self.assertEqual(rows[0]["sort_order"], 1)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertEqual(rows[0]["owner"], "employee")
        self.assertIn("corridor: IN→DE", rows[0]["notes"])
        self.assertIn("source: https://anabin.kmk.org", rows[0]["notes"])
        # No phase on the step → pre_departure default.
        self.assertEqual(rows[1]["milestone_type"], "pre_departure_ai_02")
        self.assertIsNone(rows[1]["description"])

    def test_phase_drives_milestone_type_prefix(self):
        rows = map_generated_steps_to_milestones(
            [{"order": 1, "title": "Anmeldung", "phase": "arrival"}], "IN→DE"
        )
        self.assertEqual(rows[0]["milestone_type"], "arrival_ai_01")

    def test_falls_back_to_index_and_pre_departure(self):
        rows = map_generated_steps_to_milestones(
            [{"title": "A"}, {"title": "B"}], "FR→NO"
        )
        self.assertEqual(
            [r["milestone_type"] for r in rows], ["pre_departure_ai_01", "pre_departure_ai_02"]
        )
        self.assertEqual([r["sort_order"] for r in rows], [1, 2])

    def test_empty_steps_maps_to_nothing(self):
        self.assertEqual(map_generated_steps_to_milestones([], "IN→DE"), [])
        self.assertEqual(map_generated_steps_to_milestones([{"title": ""}], "IN→DE"), [])


class PersistGeneratedMilestonesTests(unittest.TestCase):
    def test_replaces_then_writes_each_step(self):
        db = mock.MagicMock()
        written = persist_generated_milestones(db, "case-1", _STEPS, "IN→DE", request_id="rq")
        self.assertEqual(written, 2)
        # Regen preserves service-derived milestones (exclude_source='service')
        # and tags its own writes source='ai' so they're managed separately.
        db.delete_case_milestones.assert_called_once_with(
            "case-1", request_id="rq", exclude_source="service"
        )
        self.assertEqual(db.upsert_case_milestone.call_count, 2)
        first = db.upsert_case_milestone.call_args_list[0].kwargs
        self.assertEqual(first["case_id"], "case-1")
        self.assertEqual(first["milestone_type"], "immigration_ai_01")
        self.assertEqual(first["request_id"], "rq")
        self.assertEqual(first["source"], "ai")

    def test_no_op_when_no_usable_steps_does_not_delete(self):
        db = mock.MagicMock()
        written = persist_generated_milestones(db, "case-1", [], "IN→DE")
        self.assertEqual(written, 0)
        db.delete_case_milestones.assert_not_called()
        db.upsert_case_milestone.assert_not_called()


class SyntheticPhaseParsingTests(unittest.TestCase):
    """The {phase}_ai_{NN} convention must round-trip through the plan service's
    synthetic-entry fallback into the right phase block + in-phase order."""

    def test_parses_known_phase_and_sequence(self):
        from backend.relocation_plan_service import _phase_and_seq_from_synthetic_code

        self.assertEqual(_phase_and_seq_from_synthetic_code("arrival_ai_03"), ("arrival", 3))
        self.assertEqual(
            _phase_and_seq_from_synthetic_code("post_arrival_ai_10"), ("post_arrival", 10)
        )
        self.assertEqual(
            _phase_and_seq_from_synthetic_code("pre_departure_ai_01"), ("pre_departure", 1)
        )

    def test_unknown_or_legacy_code_keeps_pre_departure_default(self):
        from backend.relocation_plan_service import _phase_and_seq_from_synthetic_code

        # Unknown phase prefix → default.
        self.assertEqual(_phase_and_seq_from_synthetic_code("settlement_ai_01"), ("pre_departure", 999))
        # Legacy custom milestone (no _ai_ marker) → unchanged behaviour.
        self.assertEqual(_phase_and_seq_from_synthetic_code("some_custom_task"), ("pre_departure", 999))

    def test_ai_steps_distribute_across_phase_blocks_end_to_end(self):
        from backend.relocation_plan_service import build_phased_plan_from_milestones

        milestones = [
            {"id": "m1", "milestone_type": "immigration_ai_01", "title": "Apply for Blue Card", "status": "pending"},
            {"id": "m2", "milestone_type": "arrival_ai_02", "title": "Anmeldung", "status": "pending"},
            {"id": "m3", "milestone_type": "post_arrival_ai_03", "title": "Collect eAT", "status": "pending"},
        ]
        blocks = build_phased_plan_from_milestones(milestones)
        phases_with_tasks = {b.phase_key for b in blocks if b.tasks}
        self.assertEqual(phases_with_tasks, {"immigration", "arrival", "post_arrival"})


if __name__ == "__main__":
    unittest.main()
