"""Roadmap regeneration must see the intake HR actually wrote.

FOUND BY AN END-TO-END RUN, 2026-08-23, not by unit tests — which is the point of it.

A fresh ES→IE case was prefilled through the HR contract flow: 8 fields written, including
origin_country=ES, dest_country=IE, nationality=VE. Regeneration then produced the generic
16-step pack with no CSEP journey at all. Everything it needed was one table over:

    case_assignments.intake_draft   flat snake_case   <- W1-3 (HR prefill) WRITES here
    wizard_cases.draft_json         nested camelCase  <- W1-2 (regeneration) READ here

Different tables. They never met, and the fixture case had no wizard_cases row whatsoever, so
`_load_draft` returned {} and the corridor overlay was skipped. Both features' unit tests
passed the whole time, because each was tested against its own store.

`intake_draft_to_case_draft` (AIQ-1311) is the bridge and already existed — written so the
backend can work "straight from the reliable assignment autosave instead of depending on the
frontend having patched the right wizard_cases row".
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import roadmap_regeneration_service as svc  # noqa: E402

# The exact draft the HR prefill wrote on the fixture case (2acb3180), verbatim from prod.
HR_PREFILLED_FLAT = {
    "dest_city": "Dublin", "full_name": "Esie Fixture", "job_title": "Senior Data Engineer",
    "nationality": "VE", "origin_city": "Madrid", "dest_country": "IE",
    "contract_start": "2026-10-01", "origin_country": "ES",
    "hr_extracted_fields": ["dest_country", "origin_country"],
}


class _Db:
    """Only the one method _load_draft needs off the legacy DB seam."""

    def __init__(self, intake):
        self._intake = intake

    def get_assignment_by_case_id(self, case_id, request_id=None):
        if self._intake is None:
            return None
        return {"id": "a-1", "intake_draft": self._intake}


def _no_wizard_row(monkeypatch):
    monkeypatch.setattr(svc, "_wizard_draft", lambda case_id: {})


def _wizard_row(monkeypatch, draft):
    monkeypatch.setattr(svc, "_wizard_draft", lambda case_id: draft)


class TheHrPrefillReachesRegeneration:
    pass


class LoadDraftBridgesBothStores(unittest.TestCase):
    def setUp(self):
        import pytest  # noqa: F401  (monkeypatch used via the fixture below)

    def test_the_production_failure_case(self):
        """No wizard row + an HR-prefilled intake draft → the corridor is found."""
        import pytest
        mp = pytest.MonkeyPatch()
        try:
            _no_wizard_row(mp)
            draft = svc._load_draft(_Db(HR_PREFILLED_FLAT), "case-1")
            inputs = svc.milestone_inputs_from_draft(draft)
            self.assertEqual("ES", inputs["origin_country"])
            self.assertEqual("IE", inputs["destination_country"])
            self.assertEqual("VE", inputs["nationality"])
        finally:
            mp.undo()

    def test_before_the_fix_this_yielded_nothing(self):
        """Pins the regression itself: the wizard store alone has no corridor to offer."""
        inputs = svc.milestone_inputs_from_draft({})
        self.assertIsNone(inputs["origin_country"])
        self.assertIsNone(inputs["destination_country"])

    def test_an_intake_draft_stored_as_json_text_is_parsed(self):
        import pytest
        mp = pytest.MonkeyPatch()
        try:
            _no_wizard_row(mp)
            draft = svc._load_draft(_Db(json.dumps(HR_PREFILLED_FLAT)), "case-1")
            self.assertEqual("IE", svc.milestone_inputs_from_draft(draft)["destination_country"])
        finally:
            mp.undo()

    def test_the_employees_own_wizard_answer_wins(self):
        """An HR extraction is a proposal ABOUT the employee; their own answer outranks it."""
        import pytest
        mp = pytest.MonkeyPatch()
        try:
            _wizard_row(mp, {"relocationBasics": {"originCountry": "PT", "destCountry": "IE"}})
            draft = svc._load_draft(_Db(HR_PREFILLED_FLAT), "case-1")
            inputs = svc.milestone_inputs_from_draft(draft)
            self.assertEqual("PT", inputs["origin_country"])   # employee's, not HR's 'ES'
            self.assertEqual("IE", inputs["destination_country"])
        finally:
            mp.undo()

    def test_an_empty_wizard_skeleton_does_not_shadow_the_intake(self):
        """`_default_wizard_draft` writes {} x4. Andrea's case is exactly this: a wizard row
        that exists and says nothing. It must not mask a populated intake draft."""
        import pytest
        mp = pytest.MonkeyPatch()
        try:
            _wizard_row(mp, {"relocationBasics": {}, "employeeProfile": {},
                             "familyMembers": {}, "assignmentContext": {}})
            draft = svc._load_draft(_Db(HR_PREFILLED_FLAT), "case-1")
            inputs = svc.milestone_inputs_from_draft(draft)
            self.assertEqual("ES", inputs["origin_country"])
            self.assertEqual("IE", inputs["destination_country"])
        finally:
            mp.undo()

    def test_no_assignment_degrades_to_the_wizard_draft(self):
        import pytest
        mp = pytest.MonkeyPatch()
        try:
            _wizard_row(mp, {"relocationBasics": {"originCountry": "FR", "destCountry": "NO"}})
            draft = svc._load_draft(_Db(None), "case-1")
            self.assertEqual("FR", svc.milestone_inputs_from_draft(draft)["origin_country"])
        finally:
            mp.undo()

    def test_neither_store_is_still_safe(self):
        import pytest
        mp = pytest.MonkeyPatch()
        try:
            _no_wizard_row(mp)
            self.assertEqual({}, svc._load_draft(_Db(None), "case-1"))
        finally:
            mp.undo()

    def test_a_corrupt_intake_draft_never_raises_into_the_pipeline(self):
        import pytest
        mp = pytest.MonkeyPatch()
        try:
            _no_wizard_row(mp)
            for bad in ("not json", "[]", ""):
                self.assertEqual({}, svc._load_draft(_Db(bad), "case-1"), bad)
        finally:
            mp.undo()


class TheCorridorOverlayActuallyFires(unittest.TestCase):
    def test_the_prefilled_draft_produces_the_CSEP_journey(self):
        """End of the chain: the fix is worthless unless the overlay fires on the result."""
        import pytest
        from backend.app.services.timeline_service import compute_default_milestones
        mp = pytest.MonkeyPatch()
        try:
            _no_wizard_row(mp)
            draft = svc._load_draft(_Db(HR_PREFILLED_FLAT), "case-1")
            rows = compute_default_milestones(
                case_id="t", **svc.milestone_inputs_from_draft(draft)
            )
        finally:
            mp.undo()
        blob = " | ".join(r["title"] for r in rows)
        for marker in ("Critical Skills Employment Permit", "Employment visa", "IRP", "PPSN", "RPN"):
            self.assertIn(marker, blob, f"the CSEP journey is missing {marker!r}")
        self.assertFalse(
            [r for r in rows if r["milestone_type"] in
             {"task_visa_docs_prep", "task_visa_submit", "task_biometrics"}],
            "the superseded generic visa pack is still present",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
