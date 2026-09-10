"""Return & repatriation track — the round-trip back half of the journey.

journey-completion brief (P10): every temporary assignment ends with a return track;
a PERMANENT relocation has none. ``derive_roadmap`` pulls in no DB deps, so this runs pure.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.roadmap_builder import derive_roadmap


def _case(assignment_type=None):
    draft = {
        "relocationBasics": {"originCountry": "ES", "destCountry": "IE", "destCity": "Dublin"},
        "familyMembers": {"maritalStatus": "solo"},
    }
    if assignment_type is not None:
        draft["assignmentContext"] = {"assignmentType": assignment_type}
    return {"draft": draft}


class ReturnTrackTests(unittest.TestCase):
    def _return_track(self, result):
        return next((t for t in result["tracks"] if t["id"] == "return"), None)

    def test_temporary_assignment_gets_a_return_track(self) -> None:
        for at in ("STA", "LTA", "sta"):
            result = derive_roadmap(_case(at))
            track = self._return_track(result)
            self.assertIsNotNone(track, f"return track missing for {at}")
            self.assertEqual(track["name"], "Return & repatriation")
            self.assertIn("Return / repatriation planned", result["outcomes"])

    def test_absent_assignment_type_defaults_to_temporary(self) -> None:
        self.assertIsNotNone(self._return_track(derive_roadmap(_case(None))))

    def test_permanent_relocation_has_no_return_track(self) -> None:
        result = derive_roadmap(_case("PERMANENT"))
        self.assertIsNone(self._return_track(result))
        self.assertNotIn("Return / repatriation planned", result["outcomes"])

    def test_return_track_steps_follow_the_step_schema(self) -> None:
        track = self._return_track(derive_roadmap(_case("LTA")))
        self.assertTrue(track["steps"])
        required = {"n", "key", "title", "status", "owner", "where", "time", "cost", "depends", "line", "subs"}
        for step in track["steps"]:
            self.assertTrue(required.issubset(step.keys()), f"missing keys in {step.get('key')}")
            self.assertEqual(step["status"], "locked")
        keys = {s["key"] for s in track["steps"]}
        self.assertTrue(
            {"return-review", "return-host-exit", "return-home-reentry", "return-close"}.issubset(keys)
        )


if __name__ == "__main__":
    unittest.main()
