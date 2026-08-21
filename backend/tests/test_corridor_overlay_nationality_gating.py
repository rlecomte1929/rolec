"""The corridor overlay must not serve a free mover the third-country track.

`roadmap_corridor_overlay`'s own docstring states the invariant this file guards:

    *Gate by nationality class, never by country name.* The step graph's permit and visa
    steps apply to third-country nationals. An EEA national on the same corridor needs
    none of them.

The STEPS honoured that from the start. Three things did not, and all three were measured
against production code before this file was written:

1. **The advisories were never gated at all.** A Spanish national — a free mover into
   Ireland, who correctly receives zero immigration steps — was still told
   "a long-stay 'D' Employment visa must be applied for and GRANTED before you travel",
   and was *asserted* (`asserted: True`, not hedged) to receive a Critical Skills spouse
   permission on Stamp 1G. Two contradictory instructions in one plan.

2. **`FAMILY_REGISTRATION` was gated on family but not on nationality**, so the same free
   mover got a step whose title names Stamp 1G — a CSEP-dependant permission an EEA family
   member neither receives nor needs.

3. **Steps routed to a track that does not exist were silently dropped, but still counted
   into the headline duration.** `_TRACK_BY_STEP` puts `JOB_OFFER_CONTRACT` and
   `TRAVEL_TO_IE` in the `visa` track; `derive_roadmap` builds no visa track for a free
   mover; `_apply_corridor_overlay` skipped them with `if track is None: continue`. But
   `corridor_overlay` had already counted them into `pre_arrival_days`, and that value
   overwrites `totals.time`. Measured on `origin/main` @ 600b51c8:

       ES→IE, Spanish national   totals.time "~2 weeks"  longest rendered step 21 days
       FR→NO, French national    totals.time "1 days"    longest rendered step 21 days

   FR→NO carries 255 production cases. "1 days" is not a rounding error; it is a number a
   family plans a move around.

The third case is why `test_totals_time_is_never_shorter_than_a_rendered_step` asserts pure
arithmetic. It makes no claim about immigration law, so it cannot rot when the law changes,
and it fails loudly the moment the roadmap's headline contradicts its own contents.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./ci_test.db")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.services import roadmap_corridor_overlay as overlay  # noqa: E402
from backend.app.services.roadmap_builder import derive_roadmap  # noqa: E402


def _case(
    nationality: str,
    *,
    origin: str = "ES",
    dest: str = "IE",
    marital: str = "partner_kids",
) -> Dict[str, Any]:
    """A case shaped like the wizard's own draft. Mirrors test_roadmap_corridor_overlay."""
    return {
        "id": "case-gating",
        "status": "open",
        "draft": {
            "relocationBasics": {"originCountry": origin, "destCountry": dest},
            "employeeProfile": {"nationality": nationality, "fullName": "Test Mover"},
            "assignmentContext": {"employerName": "Test Employer"},
            "familyMembers": {
                "maritalStatus": marital,
                "spouse": {"fullName": "Partner Test"},
                "children": [{"fullName": "Child One"}, {"fullName": "Child Two"}],
            },
        },
    }


def _corridor_steps(roadmap: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        s
        for t in roadmap.get("tracks", [])
        for s in t.get("steps", [])
        if str(s.get("key", "")).startswith("corridor-")
    ]


def _advisory_ids(roadmap: Dict[str, Any]) -> List[str]:
    return [a["id"] for a in roadmap.get("advisories", [])]


#: `_humanise_days` renders "N days" under a fortnight and "~N weeks" above it.
def _time_estimate_to_days(value: str) -> int:
    m = re.fullmatch(r"(\d+) days", value.strip())
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"~(\d+) weeks", value.strip())
    if m:
        return int(m.group(1)) * 7
    raise AssertionError(f"unparseable time estimate {value!r}")


class FreeMoverIsNotServedTheThirdCountryTrack(unittest.TestCase):
    """A nationality the classifier positively resolves to EU/EEA or own-national."""

    def test_a_free_mover_gets_no_immigration_advisories(self):
        """The bug: all three ES_IE advisories were returned to a Spanish national."""
        for nationality in ("Spain", "ES", "France", "Ireland"):
            with self.subTest(nationality=nationality):
                ov = overlay.corridor_overlay(_case(nationality))
                self.assertIsNotNone(ov, "ES_IE must still resolve for a free mover")
                self.assertEqual(
                    [], ov["advisories"],
                    "a free mover needs no permit, no entry visa and no CSEP family route; "
                    "every ES_IE exception case is conditioned on the third-country path",
                )

    def test_a_free_mover_is_never_told_to_obtain_an_entry_visa(self):
        """Measured on main: VISA_REQUIRED_NATIONAL reached a Spanish national."""
        ids = _advisory_ids(derive_roadmap(_case("Spain")))
        self.assertNotIn("VISA_REQUIRED_NATIONAL", ids)
        self.assertNotIn("SPANISH_LTR_DOES_NOT_TRANSFER", ids)

    def test_a_free_mover_is_never_asserted_a_csep_family_permission(self):
        """FAMILY_REUNIFICATION_CSEP carried `asserted: True` — a stated entitlement."""
        self.assertNotIn(
            "FAMILY_REUNIFICATION_CSEP", _advisory_ids(derive_roadmap(_case("Spain")))
        )

    def test_no_served_step_mentions_stamp_1g_for_a_free_mover(self):
        """FAMILY_REGISTRATION is family-gated but was not nationality-gated."""
        roadmap = derive_roadmap(_case("Spain", marital="partner_kids"))
        offending = [
            s["title"] for s in _corridor_steps(roadmap) if "1g" in s["title"].lower()
        ]
        self.assertEqual(
            [], offending,
            "Stamp 1G is a Critical Skills dependant permission; an EEA family member "
            f"neither receives nor needs it. Served: {offending}",
        )

    def test_the_third_country_national_still_gets_the_whole_journey(self):
        """The gate must discriminate, not simply suppress. This is the control."""
        roadmap = derive_roadmap(_case("Venezuela"))
        keys = {s["key"] for s in _corridor_steps(roadmap)}
        for expected in (
            "corridor-employment_permit_application",
            "corridor-d_visa_application",
            "corridor-d_visa_granted",
            "corridor-irp_registration",
            "corridor-family_registration",
        ):
            self.assertIn(expected, keys)
        self.assertEqual(
            ["VISA_REQUIRED_NATIONAL", "SPANISH_LTR_DOES_NOT_TRANSFER",
             "FAMILY_REUNIFICATION_CSEP"],
            _advisory_ids(roadmap),
        )

    def test_an_unresolved_nationality_still_fails_open(self):
        """The overlay fails OPEN by design, and this pins that the fix did not close it.

        `classify` resolves ISO codes and EU/EEA country names but not third-country
        names, and 426 of 1389 wizard cases store a name rather than a code. Withholding
        the visa from someone we merely cannot classify is the most expensive possible
        wrong answer, so an unknown nationality must keep the full track.
        """
        for unknown in ("", "Atlantis"):
            with self.subTest(nationality=unknown):
                roadmap = derive_roadmap(_case(unknown))
                keys = {s["key"] for s in _corridor_steps(roadmap)}
                self.assertIn("corridor-d_visa_application", keys)
                self.assertIn("VISA_REQUIRED_NATIONAL", _advisory_ids(roadmap))


class TheVisaLaneHoldsOnlyImmigrationSteps(unittest.TestCase):
    """Root cause of the silent drop: two steps were filed as immigration and are not.

    `timeline_service._CORRIDOR_STEP_PHASE` — the same corridor data, one layer up — already
    classifies `JOB_OFFER_CONTRACT` as `pre_departure` and `TRAVEL_TO_IE` as `logistics`,
    against `immigration` for the permit and visa steps. Routing them to the `visa` track put
    them in a lane `_visa_track_required` does not build for a free mover, which is what made
    them droppable in the first place.
    """

    def test_signing_a_contract_and_boarding_a_plane_are_not_visa_steps(self):
        self.assertEqual("civil", overlay._TRACK_BY_STEP["JOB_OFFER_CONTRACT"])
        self.assertEqual("settlement", overlay._TRACK_BY_STEP["TRAVEL_TO_IE"])

    def test_the_visa_lane_is_exactly_the_immigration_gated_set(self):
        """Anything in the visa lane must be a step a free mover does not take.

        Keeps the two tables honest with each other: add a step to the visa lane without
        gating it, and an EEA national silently acquires an immigration step.
        """
        visa_lane = {
            sid for sid, track in overlay._TRACK_BY_STEP.items() if track == "visa"
        }
        self.assertEqual(
            set(), visa_lane - set(overlay._IMMIGRATION_GATED),
            "a step in the visa lane that is not immigration-gated would be served to a "
            "free mover under a 'Visa & Permit' heading",
        )

    def test_a_free_mover_has_no_step_in_the_visa_lane_at_all(self):
        ov = overlay.corridor_overlay(_case("Spain"))
        self.assertEqual(
            [], [s["step_id"] for s in ov["corridor_steps"] if s["track"] == "visa"]
        )


class NoComputedStepIsSilentlyDropped(unittest.TestCase):
    """Every step the overlay computes must reach a track, or the totals lie."""

    def test_every_computed_corridor_step_is_rendered(self):
        for nationality in ("Venezuela", "Spain"):
            with self.subTest(nationality=nationality):
                case = _case(nationality)
                ov = overlay.corridor_overlay(case)
                computed = {s["step_id"] for s in ov["corridor_steps"]}
                rendered = {
                    s["key"][len("corridor-"):].upper()
                    for s in _corridor_steps(derive_roadmap(case))
                }
                self.assertEqual(
                    set(), computed - rendered,
                    "steps routed to a track that does not exist were dropped while still "
                    "counting toward the headline duration",
                )

    def test_totals_time_is_never_shorter_than_a_rendered_step(self):
        """Pure arithmetic. Asserts nothing about law, so it cannot rot.

        Measured on main: FR→NO/French said "1 days" beside a 21-day step.
        """
        cases = [
            ("Venezuela", "ES", "IE"),
            ("Spain", "ES", "IE"),
            ("France", "FR", "NO"),
            ("Norway", "NO", "FR"),
        ]
        for nationality, origin, dest in cases:
            with self.subTest(nationality=nationality, corridor=f"{origin}_{dest}"):
                case = _case(nationality, origin=origin, dest=dest)
                roadmap = derive_roadmap(case)
                ov = overlay.corridor_overlay(case)
                if not ov:
                    continue
                durations = {
                    s["step_id"]: s["expected_duration_days"] for s in ov["corridor_steps"]
                }
                rendered = [
                    s["key"][len("corridor-"):].upper()
                    for s in _corridor_steps(roadmap)
                ]
                longest = max([durations.get(k, 0) for k in rendered] or [0])
                total = _time_estimate_to_days(roadmap["totals"]["time"])
                self.assertGreaterEqual(
                    total, longest,
                    f"headline duration {roadmap['totals']['time']!r} is shorter than a "
                    f"single step inside it ({longest} days)",
                )


if __name__ == "__main__":
    unittest.main()
