"""A new case must not be pre-loaded with somebody else's family.

`RelocationProfile` declared, as pydantic DEFAULTS: `familySize = 4`, `dependents =
[Child(), Child()]`, `Spouse.wantsToWork = True` and `HousingPreferences.bedroomsMin = 3`.
Every construction of `RelocationProfile(userId=...)` — and `backend/main.py` alone has
eleven, including `POST /api/hr/cases` — wrote that family of four into
`relocation_cases.profile_json`.

Measured on production 2026-08-22: **2001 of 2037 cases (98.2%)** carry all four markers
together, and **0 cases carry any other familySize**. Nothing has ever written a real one,
so the entire cluster is the schema default. That is the same finding, and the same root
cause, as the invented "Oslo, Norway" -> "Singapore" route in
test_moveplan_has_no_invented_default.py — which is why the assertions here are shaped
after it.

It is not inert:
  * `app/services/rules_engine.py:65` branches on `spouse.get("wantsToWork")` on the
    SERVING path, so a default True put spouse work-authorisation requirements on the
    roadmap of every single-person relocation;
  * `agents/compliance_engine.py`, `policy_engine.py`, `services/country_resources.py` and
    `services/resources/context_service.py` all read the same key;
  * Andrea's ES->IE case 6ecadafe reached the roadmap at intake_step=0, so nothing ever
    overwrote it and every reader saw a family of four with a working spouse.

Fails SAFE — a plausible family, never an error — so each assertion below was checked
against the pre-fix defaults and does go red there.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.schemas import (  # noqa: E402
    Child,
    HousingPreferences,
    RelocationProfile,
    Spouse,
)

# Exactly what the acceptance criterion names, plus the two currency-locked key names that
# gave the seed its "Singapore" character.
_SEED_MARKERS = ("Singapore", "Oslo")


class DefaultProfileTests(unittest.TestCase):
    def test_a_fresh_profile_asserts_no_family(self) -> None:
        profile = RelocationProfile(userId="user-1")
        self.assertIsNone(profile.familySize, "familySize still defaults to a family of four")
        self.assertEqual([], profile.dependents, "dependents still defaults to two blank children")

    def test_a_fresh_profile_invents_no_working_spouse(self) -> None:
        """The serving path reads this key — see rules_engine.apply_rules."""
        self.assertIsNone(Spouse().wantsToWork)
        self.assertIsNone(RelocationProfile(userId="u").spouse.wantsToWork)

    def test_a_fresh_profile_demands_no_bedrooms(self) -> None:
        self.assertIsNone(HousingPreferences().bedroomsMin)
        self.assertIsNone(RelocationProfile(userId="u").movePlan.housing.bedroomsMin)

    def test_the_serialised_profile_is_what_reaches_profile_json(self) -> None:
        """`model_dump()` is literally what `db.create_case` json.dumps into the column."""
        dumped = RelocationProfile(userId="user-1").model_dump()
        self.assertIsNone(dumped["familySize"])
        self.assertEqual([], dumped["dependents"])
        self.assertIsNone(dumped["spouse"]["wantsToWork"])
        self.assertIsNone(dumped["movePlan"]["housing"]["bedroomsMin"])

    def test_no_seed_place_name_survives_anywhere_in_the_blob(self) -> None:
        blob = json.dumps(RelocationProfile(userId="user-1").model_dump(), default=str)
        for marker in _SEED_MARKERS:
            self.assertNotIn(marker, blob, f"seed marker {marker!r} still written on case create")

    def test_the_move_plan_still_invents_no_route(self) -> None:
        """Guards the 2026-08-13 fix against regression from the same blob."""
        move_plan = RelocationProfile(userId="u").movePlan
        self.assertEqual("", move_plan.origin)
        self.assertEqual("", move_plan.destination)


class RealDataStillRoundTripsTests(unittest.TestCase):
    """Only the invented default is wrong. An actual family must survive untouched —
    otherwise this fix would trade one silent data error for another."""

    def test_an_explicit_family_is_preserved(self) -> None:
        profile = RelocationProfile(
            userId="u",
            familySize=3,
            dependents=[Child(firstName="Mateo")],
            spouse=Spouse(fullName="Ana", wantsToWork=True),
        )
        self.assertEqual(3, profile.familySize)
        self.assertEqual(["Mateo"], [c.firstName for c in profile.dependents])
        self.assertTrue(profile.spouse.wantsToWork)

    def test_an_explicit_single_person_is_preserved(self) -> None:
        """False must stay False and not be confused with the new None."""
        profile = RelocationProfile(userId="u", familySize=1, spouse=Spouse(wantsToWork=False))
        self.assertEqual(1, profile.familySize)
        self.assertIs(False, profile.spouse.wantsToWork)

    def test_a_stored_legacy_profile_still_parses(self) -> None:
        """2001 production rows already hold the seed; reading them must not start erroring."""
        legacy = {
            "userId": "u",
            "familySize": 4,
            "dependents": [{"firstName": None}, {"firstName": None}],
            "spouse": {"fullName": None, "wantsToWork": True},
            "movePlan": {"origin": "", "destination": "", "housing": {"bedroomsMin": 3}},
        }
        parsed = RelocationProfile(**legacy)
        self.assertEqual(4, parsed.familySize)
        self.assertEqual(3, parsed.movePlan.housing.bedroomsMin)

    def test_an_explicit_bedroom_count_is_preserved(self) -> None:
        self.assertEqual(2, HousingPreferences(bedroomsMin=2).bedroomsMin)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


# --------------------------------------------------------------------------------------
# The opt-in backfill for the 2001 rows already carrying the seed.
# --------------------------------------------------------------------------------------

import importlib.util  # noqa: E402

_BACKFILL = os.path.join(_REPO_ROOT, "backend", "scripts", "clear_seed_family_profile.py")
_spec = importlib.util.spec_from_file_location("clear_seed_family_profile", _BACKFILL)
backfill = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(backfill)


def _seeded_profile(**over):
    """Exactly what the pre-fix schema wrote — the shape of all 2001 production rows."""
    profile = {
        "userId": "u",
        "familySize": 4,
        "maritalStatus": None,
        "dependents": [
            {"firstName": None, "dateOfBirth": None, "currentGrade": None, "languageNeeds": None},
            {"firstName": None, "dateOfBirth": None, "currentGrade": None, "languageNeeds": None},
        ],
        "spouse": {"fullName": None, "nationality": None, "wantsToWork": True,
                   "occupation": None, "educationLevel": None},
        "movePlan": {"origin": "", "destination": "",
                     "housing": {"bedroomsMin": 3, "preferredAreas": [], "mustHave": []}},
    }
    profile.update(over)
    return profile


class BackfillClearsOnlyTheSeedTests(unittest.TestCase):
    def test_it_clears_a_pure_seed_row(self) -> None:
        result = backfill.clear_keys(json.dumps(_seeded_profile()))
        self.assertIsNotNone(result, "the canonical seed row was not recognised")
        updated = json.loads(result[0])
        self.assertIsNone(updated["familySize"])
        self.assertEqual([], updated["dependents"])
        self.assertIsNone(updated["spouse"]["wantsToWork"])
        self.assertIsNone(updated["movePlan"]["housing"]["bedroomsMin"])

    def test_it_touches_no_other_key(self) -> None:
        original = _seeded_profile(userId="keep-me")
        original["movePlan"]["origin"] = "Madrid, Spain"
        updated = json.loads(backfill.clear_keys(json.dumps(original))[0])
        self.assertEqual("keep-me", updated["userId"])
        self.assertEqual("Madrid, Spain", updated["movePlan"]["origin"])

    def test_a_real_family_of_four_is_never_cleared(self) -> None:
        """The whole point. These carry the same four VALUES and must survive."""
        for label, override in [
            ("spouse named", {"spouse": {"fullName": "Ana", "wantsToWork": True}}),
            ("marital status entered", {"maritalStatus": "married"}),
            ("a child named", {"dependents": [
                {"firstName": "Mateo"},
                {"firstName": None, "dateOfBirth": None, "currentGrade": None, "languageNeeds": None},
            ]}),
        ]:
            with self.subTest(label):
                self.assertIsNone(
                    backfill.clear_keys(json.dumps(_seeded_profile(**override))),
                    f"cleared a real family ({label})",
                )

    def test_housing_preferences_entered_blocks_the_clear(self) -> None:
        profile = _seeded_profile()
        profile["movePlan"]["housing"]["preferredAreas"] = ["Rathmines"]
        self.assertIsNone(backfill.clear_keys(json.dumps(profile)))

    def test_a_non_default_value_blocks_the_clear(self) -> None:
        for label, override in [
            ("familySize 2", {"familySize": 2}),
            ("one dependent", {"dependents": [{"firstName": None, "dateOfBirth": None,
                                               "currentGrade": None, "languageNeeds": None}]}),
            ("spouse does not want to work", {"spouse": {"fullName": None, "wantsToWork": False}}),
        ]:
            with self.subTest(label):
                self.assertIsNone(backfill.clear_keys(json.dumps(_seeded_profile(**override))))

    def test_already_cleared_rows_are_idempotent(self) -> None:
        """Re-running must be a no-op, not a second pass that finds new candidates."""
        once = backfill.clear_keys(json.dumps(_seeded_profile()))[0]
        self.assertIsNone(backfill.clear_keys(once))

    def test_unparseable_profile_is_skipped_not_crashed(self) -> None:
        for bad in ("", "not json", "[]", "null"):
            self.assertIsNone(backfill.clear_keys(bad), bad)
