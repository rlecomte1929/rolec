"""The roadmap must not contradict itself.

Live, in production, for an EU national relocating to Germany — the same person
whose requirements dossier correctly says "No visa or residence permit required" —
the auto-generated roadmap contained BOTH:

    #4  "Register as EU/EEA resident at local authority"
        "EU/EEA free movement: no work permit required."     <- verbatim regime notes
    #40 "Prepare visa / work permit application pack"
    #45 "Submit visa / work permit application"
    #50 "Book biometrics / appointment"

Step 4 states there is no work permit. Steps 40 and 45 tell them to file for one.

`_REGIME_MILESTONE_SPECS` is purely ADDITIVE: eu_free_movement *adds* a registration
task, while OPERATIONAL_TASK_DEFAULTS — visa prep, visa submit, biometrics — are
always appended with no suppression. The generator knows the regime and serves the
visa track anyway.

Suppression is asymmetric ON PURPOSE. We drop the visa track only when we
POSITIVELY know it does not apply (free movement, or a move that crosses no
border). An unknown nationality keeps it: under-showing a visa step to someone who
genuinely needs one is far worse than over-showing one.
"""
from __future__ import annotations

import pytest

from backend.app.services.timeline_service import compute_default_milestones

# The steps that only exist because someone is filing an immigration application.
VISA_TRACK = {
    "task_immigration_review",
    "task_visa_docs_prep",
    "task_visa_submit",
    "task_biometrics",
}


def _types(milestones):
    return {m["milestone_type"] for m in milestones}


def _by_type(milestones):
    return {m["milestone_type"]: m for m in milestones}


def _milestones(nationality, dest="GERMANY", origin="FRANCE", **kw):
    return compute_default_milestones(
        case_id="c1",
        case_draft={},
        destination_country=dest,
        origin_country=origin,
        nationality=nationality,
        target_move_date="2026-12-01",
        **kw,
    )


class TestAnEuNationalIsNotToldToApplyForAVisa:
    @pytest.mark.parametrize("nationality", ["French", "FR", "German", "Italian", "Norwegian"])
    def test_the_visa_track_is_gone(self, nationality):
        got = _types(_milestones(nationality))
        offenders = got & VISA_TRACK
        assert offenders == set(), (
            f"{nationality} has EU/EEA free movement — the roadmap must not tell them to "
            f"prepare or submit a visa/work-permit application. Got: {sorted(offenders)}"
        )

    def test_the_roadmap_says_out_loud_that_no_permit_is_required(self):
        """Suppressing silently would leave the same hole the requirements gate exists
        to close. A correct answer of "none" is a positive result and gets stated."""
        by_type = _by_type(_milestones("French"))
        assert "task_eu_registration" in by_type
        blob = f"{by_type['task_eu_registration']['title']} {by_type['task_eu_registration']['description']}"
        assert "no work permit" in blob.lower() or "no visa" in blob.lower()

    def test_nothing_left_in_the_roadmap_is_visa_framed(self):
        """The two steps that still apply — upload your ID, plan your travel — must not
        be justified by a visa the person will never hold."""
        for m in _milestones("French"):
            blob = f"{m['title']} {m.get('description') or ''}".lower()
            assert "visa validity" not in blob, m["milestone_type"]
            assert "for visa / work authorization" not in blob, m["milestone_type"]

    def test_the_genuinely_universal_steps_survive(self):
        """Free movement removes the PERMIT, not the paperwork. An EU citizen still
        registers locally, still gets a tax/social-security number, still moves house.
        Dropping those would be the mirror-image lie."""
        got = _types(_milestones("French"))
        for required in (
            "task_arrival_registration",
            "task_tax_local_registration",
            "task_settling_in",
            "task_movers_shipment",
            "task_passport_upload",
        ):
            assert required in got, f"{required} was suppressed for an EU national"


class TestAThirdCountryNationalKeepsTheVisaTrack:
    """The control. The gate must not have quietly narrowed anyone else's plan."""

    @pytest.mark.parametrize("nationality", ["Indian", "IN", "United States", "Singapore"])
    def test_the_full_visa_track_is_served(self, nationality):
        got = _types(_milestones(nationality))
        assert VISA_TRACK <= got, (
            f"{nationality} is a third-country national and needs the visa track; "
            f"missing: {sorted(VISA_TRACK - got)}"
        )


class TestUnknownNationalityFailsSafe:
    @pytest.mark.parametrize("nationality", [None, "", "asdas", "1212"])
    def test_an_unresolved_nationality_keeps_the_visa_track(self, nationality):
        """If we cannot positively know that free movement applies, we must not
        suppress. Under-showing a required visa step is the worse error."""
        got = _types(_milestones(nationality))
        assert VISA_TRACK <= got, (
            f"nationality={nationality!r} could not be resolved, so the visa track must "
            f"be kept; missing: {sorted(VISA_TRACK - got)}"
        )


class TestAnInCountryMoveHasNoImmigrationAtAll:
    """Decided by a verifiable fact — origin == destination — not by a label."""

    def test_no_visa_track_when_no_border_is_crossed(self):
        got = _types(_milestones("Indian", dest="GERMANY", origin="GERMANY"))
        offenders = got & VISA_TRACK
        assert offenders == set(), (
            "a move within one country crosses no border, so no immigration step can "
            f"apply. Got: {sorted(offenders)}"
        )

    def test_the_domestic_move_still_gets_its_real_steps(self):
        got = _types(_milestones("Indian", dest="GERMANY", origin="GERMANY"))
        assert "task_movers_shipment" in got
        assert "task_settling_in" in got
