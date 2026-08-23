"""P2-01e — case → RAG pipeline profile mapping."""
import unittest

from backend.app.services import case_roadmap_profile as crp


def _case(origin, dest, nationality=None):
    basics = {"originCountry": origin, "destCountry": dest}
    if nationality is not None:
        basics["nationality"] = nationality
    return {"id": "c1", "draft": {"relocationBasics": basics}}


class BuildCaseProfileTests(unittest.TestCase):
    def test_fr_no_eea_iso_inputs(self):
        profile, classification = crp.build_case_profile(_case("FR", "NO", "FR"))
        self.assertEqual(profile.origin_country, "FR")
        self.assertEqual(profile.destination_country, "NO")
        self.assertTrue(profile.is_eea)
        self.assertEqual(classification.corridor, "FR→NO")
        self.assertEqual(classification.pathway_type, "eu_free_movement")

    def test_country_names_normalised_to_iso2(self):
        profile, classification = crp.build_case_profile(_case("France", "Norway", "France"))
        self.assertEqual(profile.origin_country, "FR")
        self.assertEqual(profile.destination_country, "NO")
        self.assertEqual(classification.corridor, "FR→NO")
        self.assertEqual(classification.pathway_type, "eu_free_movement")

    def test_nationality_does_NOT_default_to_origin(self):
        """Was `test_nationality_defaults_to_origin`, asserting the opposite.

        The origin fallback was removed deliberately: it answered a missing
        nationality with a guess, and read 410 prod cases as EU free movers on
        the strength of their origin country alone. An unknown nationality now
        stays unknown, and unknown is not free movement — the same direction
        `nationality_class` already takes. See
        test_case_profile_nationality_source.AnUnknownNationalityFailsSafe.
        """
        profile, _ = crp.build_case_profile(_case("FR", "NO"))
        self.assertEqual(profile.nationality, "")
        self.assertFalse(profile.is_eea)

    def test_missing_country_returns_none(self):
        self.assertIsNone(crp.build_case_profile(_case("FR", None)))
        self.assertIsNone(crp.build_case_profile({"draft": {}}))
        self.assertIsNone(crp.build_case_profile({}))


if __name__ == "__main__":
    unittest.main()
