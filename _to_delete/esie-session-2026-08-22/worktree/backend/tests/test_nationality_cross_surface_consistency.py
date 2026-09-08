"""One employee, one verdict.

ReloPass answers "does this person have free movement?" in two places, with two
separate implementations:

  * the REQUIREMENTS list  -> nationality_class.classify()
  * the ROADMAP / IMMIGRATION / FAMILY path
        -> immigration_regime._is_eu_national()  (feeds case_roadmap_profile.is_eea,
           timeline_service, the regime router)
        -> family_propagation._is_eu_national()

They disagreed. `immigration_regime._EU_EEA_COUNTRIES` holds country names and ISO
codes ("france", "fr") but no ADJECTIVAL forms — and adjectival is what production
actually stores. So `classify("French", "FRANCE")` said OWN_NATIONAL (no visa
required) while `_is_eu_national("French")` said False (build them a permit
journey). The same French citizen could read "No visa or residence permit
required" on one screen while the product planned a work-permit roadmap on
another.

This file is the contradiction detector. It is written to FAIL on the divergent
implementations and pass only once every surface answers from the same brain. If
a fourth surface ever grows its own EU set, this is the test that catches it.
"""
from __future__ import annotations

import pytest

from backend.app.services.family_propagation import _is_eu_national as family_is_eu
from backend.app.services.immigration_regime import _is_eu_national as regime_is_eu
from backend.app.services.nationality_class import EU_EEA, OWN_NATIONAL, classify

# The 40 DISTINCT nationality strings actually present in production
# `wizard_cases.draft_json -> employeeProfile.nationality`. Not invented: queried.
PROD_NATIONALITIES = [
    "12", "1212", "123", "33", "asdas", "Austrian", "CA", "ccvxcv", "de", "dfgd",
    "dfgdfg", "dfgf", "dze", "ES", "ewf", "f", "fddf", "fgh", "FR", "France",
    "French", "Germany", "gh", "giu", "Hong Kong", "IN", "India", "LB", "NO",
    "norway", "Norway", "norwegian", "Norwegian", "sddvfd", "sdfsdf", "Serbian",
    "shtfryhdyt", "Singapore", "United Kingdom", "United States",
]

# Values that genuinely confer free movement into the EU/EEA. Adjectival forms are
# the ones production actually stores, and the ones the two surfaces disagreed on.
FREE_MOVEMENT_TRUTH = {
    "FR", "France", "French",
    "NO", "norway", "Norway", "norwegian", "Norwegian",
    "de", "Germany",
    "ES", "Austrian",
}

# Junk and typos. `nationality` is an unvalidated free-text field; these are all
# real values sitting in production today.
JUNK = [
    "asdas", "1212", "123", "12", "33", "ccvxcv", "dfgd", "dfgdfg", "dfgf", "dze",
    "ewf", "f", "fddf", "fgh", "giu", "sddvfd", "sdfsdf", "shtfryhdyt",
    "xx", "qq", "zz",
]

DESTINATIONS = ["FRANCE", "GERMANY", "NORWAY", "NETHERLANDS"]


def _requirements_says_free_movement(nationality: str, dest: str) -> bool:
    return classify(nationality, dest) in (OWN_NATIONAL, EU_EEA)


class TestEverySurfaceAgrees:
    """The headline invariant: one nationality, one verdict."""

    @pytest.mark.parametrize("nationality", PROD_NATIONALITIES)
    def test_requirements_and_roadmap_path_agree(self, nationality: str) -> None:
        """For an EU/EEA destination, the requirements engine and the roadmap /
        immigration path must reach the same conclusion about free movement.

        Destination is held inside the EU/EEA here because `_is_eu_national` is
        nationality-only by design — its call sites pair it with
        `_is_eu_destination(...)`. So this compares like with like.
        """
        for dest in DESTINATIONS:
            requirements = _requirements_says_free_movement(nationality, dest)
            path = regime_is_eu(nationality)
            assert requirements == path, (
                f"{nationality!r} -> {dest}: requirements say "
                f"free_movement={requirements}, but the roadmap/immigration path "
                f"says {path}. The same person would be told they need no visa on "
                f"one screen and given a permit journey on another."
            )

    @pytest.mark.parametrize("nationality", PROD_NATIONALITIES)
    def test_family_propagation_agrees_too(self, nationality: str) -> None:
        """family_propagation carries a third copy of the same predicate."""
        assert family_is_eu(nationality) == regime_is_eu(nationality), (
            f"{nationality!r}: family_propagation and immigration_regime disagree"
        )


class TestTheAdjectivalGap:
    """The specific defect, pinned so it cannot come back.

    Production stores 'French', 'Norwegian', 'Austrian' far more often than 'FR'.
    A classifier that only knows country names and ISO codes silently treats every
    one of them as a third-country national.
    """

    @pytest.mark.parametrize(
        "nationality", ["French", "Norwegian", "Austrian", "Italian", "Irish", "Spanish", "Swiss"]
    )
    def test_adjectival_eu_nationalities_have_free_movement_on_every_surface(
        self, nationality: str
    ) -> None:
        assert _requirements_says_free_movement(nationality, "FRANCE"), (
            f"{nationality} is an EU/EEA citizen"
        )
        assert regime_is_eu(nationality), (
            f"{nationality} is an EU/EEA citizen, but the roadmap/immigration path "
            "would build them a third-country permit journey"
        )

    def test_the_iso_and_adjectival_forms_of_the_same_person_agree(self) -> None:
        """'FR' and 'French' are the same human. They must not get different journeys."""
        for iso, adjectival, name in [
            ("FR", "French", "France"),
            ("NO", "Norwegian", "Norway"),
            ("DE", "German", "Germany"),
            ("CH", "Swiss", "Switzerland"),
        ]:
            verdicts = {
                iso: regime_is_eu(iso),
                adjectival: regime_is_eu(adjectival),
                name: regime_is_eu(name),
            }
            assert len(set(verdicts.values())) == 1, (
                f"the same nationality written three ways gets different verdicts: {verdicts}"
            )


class TestTheJourneyTheyActuallyGet:
    """Not just the classifier — the regime the roadmap is built from.

    Before consolidation, `detect_regime(nationality="French", destination="FRANCE")`
    returned regime_id='blue_card': the EU Blue Card, whose own note describes it as
    "highly-qualified employment route FOR A THIRD-COUNTRY NATIONAL", priority
    'critical', 12-week lead time. For a French citizen moving to France. Meanwhile
    the requirements screen correctly said "no visa or residence permit required".
    """

    @pytest.mark.parametrize(
        "nationality", ["French", "FR", "France", "Austrian", "Italian", "Norwegian", "Swiss"]
    )
    def test_an_eu_citizen_gets_the_free_movement_regime(self, nationality: str) -> None:
        from backend.app.services.immigration_regime import ImmigrationRegimeRouter

        result = ImmigrationRegimeRouter().detect_regime(
            nationality=nationality, destination_country="FRANCE"
        )
        assert result.regime_id == "eu_free_movement", (
            f"{nationality!r} is an EU/EEA citizen but was routed to "
            f"{result.regime_id!r} — a third-country work-permit journey"
        )
        assert result.typical_lead_time_weeks == 0

    @pytest.mark.parametrize("nationality", ["Indian", "United States", "asdas", None])
    def test_a_non_eu_or_unknown_national_is_never_given_free_movement(self, nationality) -> None:
        """Fails safe: an unresolved nationality must get the demanding route, not
        a free pass."""
        from backend.app.services.immigration_regime import ImmigrationRegimeRouter

        result = ImmigrationRegimeRouter().detect_regime(
            nationality=nationality, destination_country="FRANCE"
        )
        assert result.regime_id != "eu_free_movement", (
            f"{nationality!r} was granted EU free movement on the immigration path"
        )


class TestNoSurfaceMayFabricateFreeMovement:
    """The safety direction. Over-showing a visa step is a bad experience; telling
    someone they need no visa when they do is a harm. Junk must never buy free
    movement on ANY surface."""

    @pytest.mark.parametrize("nationality", JUNK)
    def test_junk_is_never_free_movement_anywhere(self, nationality: str) -> None:
        assert not _requirements_says_free_movement(nationality, "FRANCE"), (
            f"requirements: junk {nationality!r} was granted free movement"
        )
        assert not regime_is_eu(nationality), (
            f"immigration path: junk {nationality!r} was granted free movement"
        )
        assert not family_is_eu(nationality), (
            f"family propagation: junk {nationality!r} was granted free movement"
        )

    @pytest.mark.parametrize(
        "nationality", ["Indian", "IN", "India", "United States", "Singapore", "CA", "LB", "Serbian"]
    )
    def test_third_country_nationals_are_never_free_movement(self, nationality: str) -> None:
        assert not _requirements_says_free_movement(nationality, "FRANCE")
        assert not regime_is_eu(nationality)
