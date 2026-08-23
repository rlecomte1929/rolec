"""The EEA registration track is a right of the PERSON, not a property of the route.

`_build_context` decided it from geography:

    if origin_country in _EEA_COUNTRIES and dest_country in _EEA_COUNTRIES:
        visa_type = "eea_registration"

The comment above that line says "an EEA **national**" — but the code never looked at one.
Spain and Ireland are both EEA, so a **Venezuelan** moving Madrid→Dublin was typed a free
mover. `20261025000000_fam_reunion_eea_gate_es_nl_no.sql` then gates `eea_registration` out of
every family-reunification template, so a third-country national with a family was silently
denied the forms they actually need — while the person the gate was written for (an EU citizen
who genuinely does not need them) was served correctly.

`nationality_class.classify_best` has always answered this properly and the engine never
called it.

Measured on production 2026-08-23 across `wizard_cases`: 1,046 cases have BOTH ends in the
EEA and 1,025 of them (98%) carry a nationality in the draft. Of those, **14 are third-country
nationals** — 13 Indian nationals moving to Ireland, and one Venezuelan: Andrea, the first real
case. Those 14 are the entire behaviour change. ~998 EEA nationals are unaffected.

DELIBERATELY ASYMMETRIC. An unknown nationality keeps today's answer. We only stop suppressing
when we positively know the mover is third-country — never on a guess. Guessing the other way
would hand a family-reunification application to an EU citizen with a treaty right not to file
one, which is the exact harm AIQ-1795c fixed.
"""
from __future__ import annotations

import unittest

from backend.app.services.trigger_engine import _resolve_visa_type


def draft_with(nationality=None, second=None, purpose="work"):
    profile = {}
    if nationality is not None:
        profile["nationality"] = nationality
    if second is not None:
        profile["second_nationality"] = second
    return {"employeeProfile": profile, "relocationBasics": {"purpose": purpose}}


class ThirdCountryNationalOnAnEeaRoute(unittest.TestCase):
    """The bug, and the case it was found on."""

    def test_a_venezuelan_moving_madrid_to_dublin_is_not_a_free_mover(self):
        """Andrea. Both ends EEA, the person is not."""
        got = _resolve_visa_type("ES", "IE", "work", draft_with("Venezuelan"))
        self.assertNotEqual(got, "eea_registration")
        self.assertEqual(got, "skilled_worker")

    def test_an_indian_national_moving_within_the_eea_is_not_a_free_mover(self):
        """13 live cases on this exact shape."""
        self.assertNotEqual(
            _resolve_visa_type("ES", "IE", "work", draft_with("IN")), "eea_registration"
        )

    def test_an_iso_code_and_an_adjective_agree(self):
        """Intake stores both forms; they must not produce different journeys."""
        self.assertEqual(
            _resolve_visa_type("ES", "IE", "work", draft_with("VE")),
            _resolve_visa_type("ES", "IE", "work", draft_with("Venezuelan")),
        )


class EeaNationalsAreUnaffected(unittest.TestCase):
    """~998 live cases. A fix that moves these has broken far more than it repaired."""

    def test_a_french_national_moving_to_germany_still_registers(self):
        self.assertEqual(
            _resolve_visa_type("FR", "DE", "work", draft_with("French")), "eea_registration"
        )

    def test_a_spaniard_moving_to_ireland_still_registers(self):
        self.assertEqual(
            _resolve_visa_type("ES", "IE", "work", draft_with("ES")), "eea_registration"
        )

    def test_an_own_national_returning_home_still_registers(self):
        self.assertEqual(
            _resolve_visa_type("NO", "FR", "work", draft_with("French")), "eea_registration"
        )

    def test_a_dual_national_is_judged_on_the_favourable_passport(self):
        """Rights are cumulative. A Venezuelan/Italian exercises Italian free movement, and
        classifying on the Venezuelan passport alone hands them a permit track they must not
        apply for."""
        self.assertEqual(
            _resolve_visa_type("ES", "IE", "work", draft_with("Venezuelan", second="Italian")),
            "eea_registration",
        )


class UnknownNationalityKeepsTodaysAnswer(unittest.TestCase):
    """The asymmetry, stated as tests. 21 live cases have no nationality in the draft."""

    def test_a_missing_nationality_does_not_flip_the_track(self):
        self.assertEqual(
            _resolve_visa_type("FR", "DE", "work", draft_with(None)), "eea_registration"
        )

    def test_an_unrecognised_nationality_does_not_flip_the_track(self):
        """Never guess. An unparseable string is not evidence of anything."""
        self.assertEqual(
            _resolve_visa_type("FR", "DE", "work", draft_with("Wakandan")), "eea_registration"
        )

    def test_an_empty_draft_does_not_crash_and_does_not_flip(self):
        self.assertEqual(_resolve_visa_type("FR", "DE", "work", {}), "eea_registration")

    def test_a_malformed_profile_does_not_crash(self):
        self.assertEqual(
            _resolve_visa_type("FR", "DE", "work", {"employeeProfile": None}), "eea_registration"
        )


class NonEeaRoutesAreUntouched(unittest.TestCase):
    def test_a_route_with_one_end_outside_the_eea_maps_by_purpose(self):
        self.assertEqual(
            _resolve_visa_type("IN", "DE", "work", draft_with("Indian")), "skilled_worker"
        )

    def test_an_eea_national_leaving_the_eea_is_not_registering(self):
        """Free movement is a right INSIDE the union. It does not follow you to Singapore."""
        self.assertNotEqual(
            _resolve_visa_type("FR", "SG", "work", draft_with("French")), "eea_registration"
        )

    def test_purpose_still_drives_the_non_eea_answer(self):
        self.assertEqual(
            _resolve_visa_type("IN", "DE", "family_join", draft_with("Indian")), "family_join"
        )

    def test_a_missing_purpose_falls_back_to_the_draft(self):
        d = draft_with("Indian", purpose="intra_company_transfer")
        self.assertEqual(
            _resolve_visa_type("IN", "DE", "", d), "intra_company_transfer"
        )


class TheGateStillDiscriminates(unittest.TestCase):
    """Same route, two people, opposite answers. A resolver that returns one value for both
    tells the template engine nothing."""

    def test_same_corridor_opposite_verdicts(self):
        eu = _resolve_visa_type("ES", "IE", "work", draft_with("Spanish"))
        third = _resolve_visa_type("ES", "IE", "work", draft_with("Venezuelan"))
        self.assertEqual(eu, "eea_registration")
        self.assertNotEqual(third, "eea_registration")
        self.assertNotEqual(eu, third)


if __name__ == "__main__":
    unittest.main()
