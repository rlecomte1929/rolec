"""
[AIQ-1881 / T18-07] The employee immigration surface must not dead-end.

GET /api/employee/cases/{id}/immigration used to 404 with

    "No immigration case found for this relocation. Contact your HR team."

on a case where the employee was assigned and had submitted intake. That is a
loop, not an empty state: HR's own available-forms and milestones came back empty
for the same case, and NOTHING in the product ever calls
POST /api/hr/immigration/cases. She was told to ask someone who had nothing to give.

Verified in prod 2026-08-20: immigration_cases holds 4 rows, newest 2026-05-27,
against 1,156 case_assignments — so essentially every real case 404s.

It now returns 200 with a state derived from what we actually know:

  open                — a case exists (unchanged shape, plus `state`)
  no_permit_required  — free movement: the CORRECT and COMPLETE answer
  awaiting_hr         — a permit is needed and nobody has opened the file
  coverage_gap        — we cannot categorise; we say so rather than guess

An immigration case is deliberately NOT created implicitly: `permit_type` is
mandatory and validated, and a free-movement national has no permit to track.

Second defect fixed here: the lookup keyed on the RAW path id while all 4
production rows key on the canonical case id, and this route's path param may
carry either form (its own ownership check matches `id = :case_id OR
case_id = :case_id`). That is the AIQ-1704 failure — a row that exists but is
never found.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import immigration_status as mod  # noqa: E402

_HR = {"id": str(uuid.uuid4()), "role": "HR", "is_admin": False}


class AbsentStateTests(unittest.TestCase):
    """_absent_immigration_case_state is the whole decision — test it directly."""

    def _state(self, nationality, dest):
        with mock.patch.object(mod, "_get_case_details", return_value={"dest_country": dest}), \
             mock.patch(
                 "backend.app.services.wizard_draft_mapper.extract_profile_from_wizard_draft",
                 return_value={"nationality": nationality},
             ), \
             mock.patch(
                 "backend.app.services.relocation_plan_view_service.load_profile_draft_for_case",
                 return_value={},
             ), \
             mock.patch("backend.app.db.SessionLocal"):
            return mod._absent_immigration_case_state("case-1")

    def test_eu_national_is_told_they_need_nothing_not_to_contact_hr(self) -> None:
        """The Madrid->Dublin case this ticket came from. 'No permit required' is a
        complete answer; telling her to contact HR invents a problem she has not got."""
        s = self._state("Spanish", "IRELAND")
        self.assertEqual(s["state"], "no_permit_required")
        self.assertEqual(s["nationality_class"], "EU_EEA")
        self.assertIsNone(s["next_action"])
        blob = (s["headline"] + s["detail"]).lower()
        self.assertNotIn("contact your hr", blob)
        self.assertNotIn("contact hr", blob)

    def test_third_country_national_is_told_who_acts_next(self) -> None:
        s = self._state("Indian", "IRELAND")
        self.assertEqual(s["state"], "awaiting_hr")
        self.assertEqual(s["nationality_class"], "THIRD_COUNTRY")
        self.assertTrue(s["next_action"], "no next action named")

    def test_own_national_needs_no_permit(self) -> None:
        s = self._state("Irish", "IRELAND")
        self.assertEqual(s["state"], "no_permit_required")

    def test_unclassifiable_nationality_never_asserts_a_permit_requirement(self) -> None:
        """`classify` returns None for forms outside its lookup tables. Claiming "a
        permit is needed" would assert a requirement we have not established;
        claiming the opposite would be far worse.

        [AIQ-2033] This used "Venezuelan", which resolves now that the adjectival and
        country-name tables were made symmetric — Andrea, the first real ES->IE case,
        is Venezuelan and no longer lands here. Moved to a nationality the tables
        still do not know, so the branch stays covered."""
        s = self._state("Brazilian", "IRELAND")
        self.assertEqual(s["state"], "coverage_gap")
        self.assertIsNone(s["nationality_class"])
        self.assertTrue(s["next_action"])

    def test_unknown_nationality_is_a_coverage_gap_never_free_movement(self) -> None:
        """Fail closed. Treating an unknown nationality as free movement would tell a
        visa-required employee she needs nothing — the most expensive possible wrong answer."""
        s = self._state(None, "IRELAND")
        self.assertEqual(s["state"], "coverage_gap")
        self.assertIsNone(s["nationality_class"])
        self.assertIn("nationality", s["detail"].lower())

    def test_unknown_destination_is_a_coverage_gap(self) -> None:
        s = self._state("Spanish", None)
        self.assertEqual(s["state"], "coverage_gap")

    def test_every_state_carries_renderable_copy(self) -> None:
        """Criterion 1 — a state the UI can render, and criterion 3 — copy that names
        the next action rather than deferring to HR."""
        for nationality, dest in [("Spanish", "IRELAND"), ("Indian", "IRELAND"),
                                  ("Venezuelan", "IRELAND"), (None, "IRELAND"),
                                  ("Spanish", None)]:
            s = self._state(nationality, dest)
            self.assertTrue(s["headline"], f"{nationality}/{dest}: no headline")
            self.assertTrue(s["detail"], f"{nationality}/{dest}: no detail")
            self.assertIsNone(s["immigration_case"])
            self.assertIn("state", s)

    def test_never_raises_when_lookups_fail(self) -> None:
        """A resources/immigration surface must degrade, never 500."""
        with mock.patch.object(mod, "_get_case_details", side_effect=RuntimeError("db down")), \
             mock.patch("backend.app.db.SessionLocal", side_effect=RuntimeError("db down")):
            s = mod._absent_immigration_case_state("case-1")
        self.assertEqual(s["state"], "coverage_gap")


class CanonicalCaseIdTests(unittest.TestCase):
    def test_resolves_to_the_canonical_id(self) -> None:
        canonical = str(uuid.uuid4())
        ids = mock.Mock(canonical_case_id=canonical)
        with mock.patch.object(mod.db, "resolve_case_ids", return_value=ids):
            self.assertEqual(mod._canonical_case_id("some-assignment-id"), canonical)

    def test_falls_back_to_the_argument_when_unresolvable(self) -> None:
        """Best-effort: an unresolvable id must not turn a readable page into an error."""
        with mock.patch.object(mod.db, "resolve_case_ids", return_value=None):
            self.assertEqual(mod._canonical_case_id("raw-id"), "raw-id")

    def test_falls_back_when_resolution_raises(self) -> None:
        with mock.patch.object(mod.db, "resolve_case_ids", side_effect=RuntimeError("boom")):
            self.assertEqual(mod._canonical_case_id("raw-id"), "raw-id")


if __name__ == "__main__":
    unittest.main()
