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
    },
    {
        "order": 2,
        "title": "Submit EU Blue Card application (Type D visa)",
        "description": None,
        "confidence": "high",
        "requires_expert_review": True,
    },
    {"order": 3, "title": "   ", "description": "blank title — dropped"},
]


class MapGeneratedStepsTests(unittest.TestCase):
    def test_maps_steps_to_milestone_kwargs(self):
        rows = map_generated_steps_to_milestones(_STEPS, "IN→DE")
        # The blank-title step is dropped.
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["milestone_type"], "ai_01")
        self.assertEqual(rows[0]["title"], "Verify qualification via Anabin")
        self.assertEqual(rows[0]["description"], "Check the German Anabin database for H+ status.")
        self.assertEqual(rows[0]["sort_order"], 1)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertEqual(rows[0]["owner"], "employee")
        self.assertIn("corridor: IN→DE", rows[0]["notes"])
        self.assertIn("source: https://anabin.kmk.org", rows[0]["notes"])
        self.assertEqual(rows[1]["milestone_type"], "ai_02")
        self.assertIsNone(rows[1]["description"])

    def test_falls_back_to_index_when_order_missing(self):
        rows = map_generated_steps_to_milestones(
            [{"title": "A"}, {"title": "B"}], "FR→NO"
        )
        self.assertEqual([r["milestone_type"] for r in rows], ["ai_01", "ai_02"])
        self.assertEqual([r["sort_order"] for r in rows], [1, 2])

    def test_empty_steps_maps_to_nothing(self):
        self.assertEqual(map_generated_steps_to_milestones([], "IN→DE"), [])
        self.assertEqual(map_generated_steps_to_milestones([{"title": ""}], "IN→DE"), [])


class PersistGeneratedMilestonesTests(unittest.TestCase):
    def test_replaces_then_writes_each_step(self):
        db = mock.MagicMock()
        written = persist_generated_milestones(db, "case-1", _STEPS, "IN→DE", request_id="rq")
        self.assertEqual(written, 2)
        db.delete_case_milestones.assert_called_once_with("case-1", request_id="rq")
        self.assertEqual(db.upsert_case_milestone.call_count, 2)
        first = db.upsert_case_milestone.call_args_list[0].kwargs
        self.assertEqual(first["case_id"], "case-1")
        self.assertEqual(first["milestone_type"], "ai_01")
        self.assertEqual(first["request_id"], "rq")

    def test_no_op_when_no_usable_steps_does_not_delete(self):
        db = mock.MagicMock()
        written = persist_generated_milestones(db, "case-1", [], "IN→DE")
        self.assertEqual(written, 0)
        db.delete_case_milestones.assert_not_called()
        db.upsert_case_milestone.assert_not_called()


if __name__ == "__main__":
    unittest.main()
