"""
P2-07e — roadmap step estimated_effort derivation + the additive contract fields.

Pure/contract-level tests (no DB): the effort heuristic is deterministic, and the
RoadmapStepV2 model carries the two new optional fields with safe defaults.
"""
from __future__ import annotations

import unittest

from backend.app.routers.cases_read import RoadmapStepV2, _derive_estimated_effort


class DeriveEstimatedEffortTests(unittest.TestCase):
    def test_buckets_by_doc_count(self):
        self.assertEqual(_derive_estimated_effort(0), "~15 min")
        self.assertEqual(_derive_estimated_effort(1), "~1 hour")
        self.assertEqual(_derive_estimated_effort(2), "~1 hour")
        self.assertEqual(_derive_estimated_effort(3), "Half a day")
        self.assertEqual(_derive_estimated_effort(9), "Half a day")

    def test_deterministic_and_handles_negative(self):
        self.assertEqual(_derive_estimated_effort(-1), "~15 min")          # defensive
        self.assertEqual(_derive_estimated_effort(2), _derive_estimated_effort(2))  # stable


class RoadmapStepV2ContractTests(unittest.TestCase):
    def test_new_fields_present_and_default_none(self):
        step = RoadmapStepV2(id="s1", title="T", status="pending", owner="employee", sort_order=0)
        self.assertIn("estimated_effort", step.model_fields)
        self.assertIn("confidence", step.model_fields)
        self.assertIsNone(step.estimated_effort)
        self.assertIsNone(step.confidence)

    def test_fields_round_trip_and_are_additive(self):
        step = RoadmapStepV2(
            id="s1", title="T", status="pending", owner="employee", sort_order=0,
            estimated_effort="~1 hour", confidence="high",
        )
        dumped = step.model_dump()
        self.assertEqual(dumped["estimated_effort"], "~1 hour")
        self.assertEqual(dumped["confidence"], "high")
        # existing contract guard still holds (dependency_ids default [])
        self.assertEqual(dumped["dependency_ids"], [])


if __name__ == "__main__":
    unittest.main()
