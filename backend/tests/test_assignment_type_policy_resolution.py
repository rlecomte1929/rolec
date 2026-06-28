"""AIQ-1349 PR2 — the assignment_type captured at intake (PR1, written to
``assignmentContext.assignmentType`` on the case draft) drives the policy
resolution context, so STA / LTA / PERMANENT resolve to DISTINCT applicable
benefits via the already-wired resolver.

This proves the intake→policy seam: ``_intake_overlay_from_case_draft`` surfaces
``assignmentType`` and ``extract_resolution_context`` normalizes it. The actual
benefit *set* difference is policy-data-dependent; this asserts the deterministic
seam (the value the STA/LTA-aware resolver receives).
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_resolution import extract_resolution_context


def _ctx_for(assignment_type: str):
    draft = {
        "relocationBasics": {"destCountry": "DE", "destCity": "Berlin"},
        "familyMembers": {"maritalStatus": "single"},
        "assignmentContext": {"assignmentType": assignment_type, "jobTitle": "Engineer"},
    }
    return extract_resolution_context({}, None, draft, {})


class AssignmentTypePolicyResolutionTests(unittest.TestCase):
    def test_intake_assignment_type_drives_distinct_resolution_context(self) -> None:
        sta = _ctx_for("STA")["assignment_type"]
        lta = _ctx_for("LTA")["assignment_type"]
        perm = _ctx_for("PERMANENT")["assignment_type"]
        self.assertEqual(sta, "STA")
        self.assertEqual(lta, "LTA")
        self.assertEqual(perm, "PERMANENT")
        # M2: STA and LTA reach the resolver as DIFFERENT types → benefits can differ.
        self.assertNotEqual(sta, lta)

    def test_explicit_assignment_type_overrides_contract_type_inference(self) -> None:
        # An explicit STA from the new intake control wins over a legacy
        # contractType='permanent' guess.
        draft = {
            "relocationBasics": {"destCountry": "DE"},
            "familyMembers": {},
            "assignmentContext": {"assignmentType": "STA", "contractType": "permanent"},
        }
        self.assertEqual(extract_resolution_context({}, None, draft, {})["assignment_type"], "STA")

    def test_absent_assignment_type_defaults_to_lta(self) -> None:
        draft = {"relocationBasics": {"destCountry": "DE"}, "familyMembers": {}, "assignmentContext": {}}
        self.assertEqual(extract_resolution_context({}, None, draft, {})["assignment_type"], "LTA")


if __name__ == "__main__":
    unittest.main()
