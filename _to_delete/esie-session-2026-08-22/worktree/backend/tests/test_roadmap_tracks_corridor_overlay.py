"""The corridor journey must reach the roadmap the employee actually opens.

AIQ-1867 taught `roadmap_builder.derive_roadmap` to fold a corridor's authored step graph
into the roadmap. It works. It is also, on the employee's screen, invisible — because
`derive_roadmap` serves `GET /api/cases/{id}/roadmap` (v1), and **v1 has no frontend
caller**. `frontend/src/api/roadmap.ts::getCaseRoadmap` is defined and referenced nowhere;
`EmployeeCaseRoadmapPage` and `EmployeeTaskPage` both call `getCaseRoadmapV2`, which hits
`GET /api/cases/{id}/roadmap/tracks` — an endpoint projected from `case_forms` that read no
corridor asset at all.

So the CSEP permit chain, the long-stay 'D' visa, the Stamp 1G family route and every
advisory reached the plan email and the HR timeline, and never the person moving. This
module tests the join that fixes that.

The tests drive `merge_corridor_overlay_v2` directly rather than the endpoint: the function
is pure over (tracks, draft), so no DB, no auth and no HTTP client is needed, and a failure
points at the merge instead of at a fixture.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./ci_test.db")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.routers.cases_read import (  # noqa: E402
    RoadmapStepV2,
    RoadmapTrackV2,
    merge_corridor_overlay_v2,
)


def _draft(
    nationality: str = "Venezuela",
    *,
    origin: str = "ES",
    dest: str = "IE",
    marital: str = "partner_kids",
) -> Dict[str, Any]:
    """Andrea's shape: a Venezuelan national, Madrid → Dublin, spouse + two children."""
    return {
        "relocationBasics": {"originCountry": origin, "destCountry": dest},
        "employeeProfile": {"nationality": nationality, "fullName": "Andrea Test"},
        "assignmentContext": {"employerName": "Google"},
        "familyMembers": {
            "maritalStatus": marital,
            "spouse": {"fullName": "Partner Test"},
            "children": [{"fullName": "Child One"}, {"fullName": "Child Two"}],
        },
    }


def _form_track(key: str = "civil", *, n_steps: int = 1, status: str = "completed"):
    """A track as `project_tracks` would have produced it from real case_forms."""
    return RoadmapTrackV2(
        id=key, name=key.title(), icon="document", sort_order=1,
        progress_pct=100 if status == "completed" else 0,
        steps=[
            RoadmapStepV2(
                id=f"form-{key}-{i}", title=f"Existing form {i}", status=status,
                owner="employee", sort_order=i,
            )
            for i in range(n_steps)
        ],
    )


def _ids(tracks: List[RoadmapTrackV2]) -> List[str]:
    return [s.id for t in tracks for s in t.steps]


class TheCorridorJourneyReachesTheEmployeeScreen(unittest.TestCase):

    def test_a_third_country_national_gets_the_whole_csep_chain(self):
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        ids = _ids(tracks)
        for expected in (
            "corridor-job_offer_contract",
            "corridor-employment_permit_application",
            "corridor-employment_permit_granted",
            "corridor-d_visa_application",
            "corridor-d_visa_granted",
            "corridor-travel_to_ie",
            "corridor-irp_registration",
            "corridor-ppsn",
            "corridor-revenue_registration",
            "corridor-family_registration",
            "corridor-stamp4_eligibility",
        ):
            self.assertIn(expected, ids)

    def test_the_advisories_reach_the_response(self):
        advisories = merge_corridor_overlay_v2([], _draft())
        self.assertEqual(
            ["VISA_REQUIRED_NATIONAL", "SPANISH_LTR_DOES_NOT_TRANSFER",
             "FAMILY_REUNIFICATION_CSEP"],
            [a.id for a in advisories],
        )

    def test_an_unresolved_condition_is_never_marked_asserted(self):
        """The honesty bit. `visa_required_nationality` is a lookup this repo does not hold."""
        by_id = {a.id: a for a in merge_corridor_overlay_v2([], _draft())}
        self.assertFalse(by_id["VISA_REQUIRED_NATIONAL"].asserted)
        self.assertFalse(by_id["SPANISH_LTR_DOES_NOT_TRANSFER"].asserted)
        # This one we CAN resolve — the household is in the draft.
        self.assertTrue(by_id["FAMILY_REUNIFICATION_CSEP"].asserted)

    def test_corridor_steps_never_claim_confidence_they_cannot_back(self):
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        corridor = [s for t in tracks for s in t.steps if s.id.startswith("corridor-")]
        self.assertTrue(corridor)
        for s in corridor:
            self.assertEqual("UNKNOWN", s.confidence_level)
            self.assertIsNone(s.source_url)

    def test_a_forward_looking_fact_is_never_an_employee_task(self):
        """`EmployeeTaskPage` builds the task list from `owner === 'employee'`.

        STAMP4_ELIGIBILITY is `outcome_type: nothing_to_do` — after 21 months on a Critical
        Skills permit there is no renewal to file. It belongs on the roadmap (it is one of
        the corridor's flagged non-obvious facts, and a welcome one) but a task nobody can
        ever tick stays open forever.
        """
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        by_id = {s.id: s for t in tracks for s in t.steps}
        stamp4 = by_id["corridor-stamp4_eligibility"]
        self.assertEqual("informational", stamp4.owner)
        self.assertNotEqual("employee", stamp4.owner)
        # …and it is still on the roadmap, not silently dropped.
        self.assertIn("Stamp 4", stamp4.title)

    def test_the_steps_that_are_hers_are_still_hers(self):
        """Control: the gate must discriminate, not blanket-demote."""
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        by_id = {s.id: s for t in tracks for s in t.steps}
        self.assertEqual("employee", by_id["corridor-d_visa_application"].owner)
        self.assertEqual("employee", by_id["corridor-ppsn"].owner)
        # The employer files the permit; DETE grants it. Neither is her task.
        self.assertEqual("employer", by_id["corridor-employment_permit_application"].owner)
        self.assertEqual("authority", by_id["corridor-employment_permit_granted"].owner)

    def test_a_free_mover_gets_no_visa_track_and_no_advisories(self):
        tracks: List[RoadmapTrackV2] = []
        advisories = merge_corridor_overlay_v2(tracks, _draft("Spain"))
        self.assertEqual([], advisories)
        self.assertNotIn("visa", [t.id for t in tracks])
        ids = _ids(tracks)
        self.assertNotIn("corridor-d_visa_application", ids)
        self.assertNotIn("corridor-family_registration", ids)
        # …but the steps that are not immigration acts are still there.
        self.assertIn("corridor-job_offer_contract", ids)
        self.assertIn("corridor-travel_to_ie", ids)


class TheMergeDoesNotCorruptWhatWasAlreadyThere(unittest.TestCase):

    def test_existing_form_steps_survive(self):
        tracks = [_form_track("civil", n_steps=2)]
        merge_corridor_overlay_v2(tracks, _draft())
        ids = _ids(tracks)
        self.assertIn("form-civil-0", ids)
        self.assertIn("form-civil-1", ids)

    def test_a_finished_track_stops_claiming_100_percent_once_it_grows(self):
        """The bug this guards: progress_pct came from the forms alone.

        A civil track at 100% that gains a pending corridor step is not complete, and
        telling someone it is means they stop looking at it.
        """
        tracks = [_form_track("civil", n_steps=1, status="completed")]
        self.assertEqual(100, tracks[0].progress_pct)
        merge_corridor_overlay_v2(tracks, _draft())
        civil = next(t for t in tracks if t.id == "civil")
        self.assertGreater(len(civil.steps), 1)
        self.assertLess(civil.progress_pct, 100)

    def test_tracks_come_back_in_sort_order(self):
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        orders = [t.sort_order for t in tracks]
        self.assertEqual(sorted(orders), orders)

    def test_no_corridor_pathway_changes_nothing(self):
        """Fallback-safe: an unknown corridor must leave the roadmap exactly as it was."""
        tracks = [_form_track("civil", n_steps=2)]
        before = _ids(tracks)
        advisories = merge_corridor_overlay_v2(tracks, _draft(origin="XX", dest="ZZ"))
        self.assertEqual([], advisories)
        self.assertEqual(before, _ids(tracks))

    def test_a_malformed_draft_never_raises(self):
        for bad in ({}, {"relocationBasics": None}, {"relocationBasics": {"originCountry": None}}):
            with self.subTest(draft=bad):
                tracks = [_form_track("civil")]
                self.assertEqual([], merge_corridor_overlay_v2(tracks, bad))
                self.assertEqual(["form-civil-0"], _ids(tracks))


if __name__ == "__main__":
    unittest.main()


# ── the "easy to miss" trap notes reach the roadmap the mover opens ──────────────────

class NonObviousStepNotesReachTheRoadmap(unittest.TestCase):
    """Seven CSEP steps are flagged `non_obvious: true` with an authored explanation.

    The loader parses both the flag and the note, but the overlay used to drop them — the
    exact analogue of the advisories bug #1953 fixed, one layer down. Without them the mover
    sees a bare step title and none of the reason it matters: the emergency-tax 40% rate, the
    proof-of-address catch-22, the ordinarily-resident health test.
    """

    def test_the_emergency_tax_rate_reaches_the_step(self):
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        by_id = {s.id: s for t in tracks for s in t.steps}
        revenue = by_id["corridor-revenue_registration"]
        self.assertTrue(revenue.non_obvious)
        self.assertIn("40%", revenue.non_obvious_note or "")
        self.assertIn("week five", (revenue.non_obvious_note or "").lower())

    def test_the_proof_of_address_catch22_reaches_the_step(self):
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        bank = {s.id: s for t in tracks for s in t.steps}["corridor-bank_account"]
        self.assertTrue(bank.non_obvious)
        self.assertIn("proof of address", (bank.non_obvious_note or "").lower())

    def test_exactly_the_seven_flagged_steps_carry_a_note(self):
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        flagged = {
            s.id for t in tracks for s in t.steps
            if s.id.startswith("corridor-") and s.non_obvious
        }
        self.assertEqual(
            {
                "corridor-employment_permit_granted",
                "corridor-d_visa_application",
                "corridor-irp_registration",
                "corridor-revenue_registration",
                "corridor-bank_account",
                "corridor-health_setup",
                "corridor-stamp4_eligibility",
            },
            flagged,
        )
        for t in tracks:
            for s in t.steps:
                if s.non_obvious:
                    self.assertTrue(
                        (s.non_obvious_note or "").strip(),
                        f"{s.id} is flagged non_obvious but carries no explanation",
                    )

    def test_a_routine_step_is_not_flagged(self):
        """The gate discriminates: JOB_OFFER_CONTRACT and PPSN are not traps."""
        tracks: List[RoadmapTrackV2] = []
        merge_corridor_overlay_v2(tracks, _draft())
        by_id = {s.id: s for t in tracks for s in t.steps}
        self.assertFalse(by_id["corridor-ppsn"].non_obvious)
        self.assertIsNone(by_id["corridor-ppsn"].non_obvious_note)
