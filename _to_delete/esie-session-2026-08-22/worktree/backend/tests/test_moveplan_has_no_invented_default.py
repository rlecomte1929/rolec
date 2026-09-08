"""`MovePlan` must not invent a route, and the policy resolver must not invent a city.

`backend/schemas.py` declared `MovePlan.origin = "Oslo, Norway"` and
`destination = "Singapore"` as pydantic DEFAULTS. Anything constructing a MovePlan without
setting them wrote that pair into `relocation_cases.profile_json` — **1365 of 1401 production
cases (97.4%)** carried it, including Paris->Oslo cases on the FR-NO corridor.

It was not inert. `frontend/src/features/cases/caseEssentials.ts` resolves
`nonEmpty(movePlan.origin) ?? nonEmpty(caseOriginHint)` — movePlan FIRST — so a non-empty
default beat the real route wherever one existed, and `HrCaseSummary` rendered
"Oslo, Norway -> Singapore" for a case that was nothing of the sort.

`hr_policy_resolver._extract_city` hardcoded the same invented pair a second time, as the
fallback for the movers criteria.

This fails SAFE — you get a plausible-looking route, never an error — so each test here was
checked against the pre-fix code and does go red.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.schemas import MovePlan  # noqa: E402
from backend.app.services.hr_policy_resolver import _extract_city  # noqa: E402

_INVENTED = {"oslo", "oslo, norway", "singapore"}


class MovePlanDefaultsTests(unittest.TestCase):
    def test_default_move_plan_invents_no_route(self):
        mp = MovePlan()
        self.assertEqual("", mp.origin)
        self.assertEqual("", mp.destination)

    def test_serialised_default_carries_no_place_name(self):
        """The serialised shape is what reaches profile_json and then the UI."""
        dumped = MovePlan().model_dump() if hasattr(MovePlan(), "model_dump") else MovePlan().dict()
        for key in ("origin", "destination"):
            self.assertNotIn(
                str(dumped[key]).strip().lower(), _INVENTED,
                f"MovePlan().{key} still serialises an invented place name",
            )

    def test_explicit_values_are_preserved(self):
        """Only the invented default is wrong — a real move plan must still round-trip."""
        mp = MovePlan(origin="Paris, France", destination="Oslo, Norway")
        self.assertEqual("Paris, France", mp.origin)
        self.assertEqual("Oslo, Norway", mp.destination)


class ExtractCityTests(unittest.TestCase):
    def test_missing_profile_yields_unknown_not_a_city(self):
        self.assertEqual("", _extract_city(None, "origin"))
        self.assertEqual("", _extract_city(None, "destination"))

    def test_absent_move_plan_yields_unknown_not_a_city(self):
        self.assertEqual("", _extract_city({}, "origin"))
        self.assertEqual("", _extract_city({"movePlan": {}}, "destination"))

    def test_empty_string_is_not_replaced_by_a_default(self):
        profile = {"movePlan": {"origin": "", "destination": ""}}
        self.assertEqual("", _extract_city(profile, "origin"))
        self.assertEqual("", _extract_city(profile, "destination"))

    def test_real_city_is_returned_and_country_suffix_trimmed(self):
        profile = {"movePlan": {"origin": "Paris, France", "destination": "Bergen"}}
        self.assertEqual("Paris", _extract_city(profile, "origin"))
        self.assertEqual("Bergen", _extract_city(profile, "destination"))


if __name__ == "__main__":
    unittest.main()
