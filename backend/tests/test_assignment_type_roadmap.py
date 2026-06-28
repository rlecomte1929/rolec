"""AIQ-1349 PR3 — assignment_type captured at intake flows into roadmap
generation so the (LLM) generator can tailor a temporary assignment's steps.

Deterministic seams (the LLM step-pruning itself is verified out of band):
1. build_case_profile lifts assignmentContext.assignmentType onto PathClassification.
2. _build_context_message renders it into the SUBJECT block the prompt reads.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.case_roadmap_profile import build_case_profile
from backend.app.services.immigration_retriever import PathClassification, UserProfile
from backend.app.services.roadmap_generator import _build_context_message


class AssignmentTypeRoadmapTests(unittest.TestCase):
    def test_build_case_profile_carries_assignment_type(self) -> None:
        case = {
            "draft": {
                "relocationBasics": {"originCountry": "FR", "destCountry": "NO"},
                "assignmentContext": {"assignmentType": "STA"},
            }
        }
        mapping = build_case_profile(case)
        self.assertIsNotNone(mapping)
        _profile, classification = mapping
        self.assertEqual(classification.assignment_type, "STA")

    def test_build_case_profile_assignment_type_absent_is_none(self) -> None:
        case = {"draft": {"relocationBasics": {"originCountry": "FR", "destCountry": "NO"}}}
        mapping = build_case_profile(case)
        self.assertIsNotNone(mapping)
        _profile, classification = mapping
        self.assertIsNone(classification.assignment_type)

    def test_context_message_includes_assignment_type(self) -> None:
        prof = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
        sta = PathClassification(pathway_type="eu_free_movement", corridor="FR→NO", assignment_type="STA")
        msg = _build_context_message(prof, sta, [], "FR→NO")
        self.assertIn("assignment_type=STA", msg)

    def test_context_message_defaults_to_lta_when_absent(self) -> None:
        prof = UserProfile(nationality="FR", origin_country="FR", destination_country="NO", is_eea=True)
        cls = PathClassification(pathway_type="eu_free_movement", corridor="FR→NO")
        msg = _build_context_message(prof, cls, [], "FR→NO")
        self.assertIn("assignment_type=LTA", msg)


if __name__ == "__main__":
    unittest.main()
