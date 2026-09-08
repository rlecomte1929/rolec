"""The Oslo->Singapore backfill must never clear a genuine Oslo->Singapore case.

`clear_invented_move_plan.py` blanks `movePlan.origin/destination` on the 1365 production cases
that carry the old pydantic defaults. The dangerous failure is not missing a row — it is
clearing a REAL move plan, which destroys user data and cannot be distinguished afterwards from
a case that never had one.

So the filter is two-sided: the pair must be exactly the invented one, AND the case's own route
columns must contradict it. Absence of route data is not a contradiction — an unknown route is
no evidence that the stored one is wrong.

These test the pure decision functions; no DB.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.scripts.clear_invented_move_plan import (  # noqa: E402
    INVENTED_DESTINATION,
    INVENTED_ORIGIN,
    clear_keys,
    contradicts,
    is_untouched_move_plan,
)


def _profile(origin=INVENTED_ORIGIN, destination=INVENTED_DESTINATION, extra=None):
    mp = {"origin": origin, "destination": destination, "targetArrivalDate": "2026-10-01"}
    if extra:
        mp.update(extra)
    return json.dumps({"movePlan": mp, "familySize": 4})


class ContradictsTests(unittest.TestCase):
    def test_fr_no_case_contradicts_and_is_cleared(self):
        """The real production shape: Paris -> Oslo on the FR-NO corridor."""
        hit, reason = contradicts(
            {"corridor": "FR-NO", "origin_city": "Paris", "dest_city": "Oslo"}
        )
        self.assertTrue(hit, reason)

    def test_a_genuine_oslo_to_singapore_case_is_left_alone(self):
        """THE case this filter exists to protect."""
        hit, reason = contradicts({
            "corridor": "NO-SG", "origin_city": "Oslo", "dest_city": "Singapore",
            "origin_country_code": "NO", "dest_country_code": "SG",
        })
        self.assertFalse(hit, reason)

    def test_no_route_data_is_not_a_contradiction(self):
        hit, reason = contradicts({"corridor": None, "origin_city": None, "dest_city": None})
        self.assertFalse(hit)
        self.assertIn("no route data", reason)

    def test_destination_alone_can_contradict(self):
        hit, _ = contradicts({"dest_country_code": "IE"})
        self.assertTrue(hit)

    def test_origin_alone_can_contradict(self):
        hit, _ = contradicts({"origin_country_code": "ES"})
        self.assertTrue(hit)

    def test_country_synonyms_do_not_false_positive(self):
        """'Norway' and 'NO' must both count as agreeing with 'Oslo, Norway'."""
        self.assertFalse(contradicts({"home_country": "Norway", "host_country": "Singapore"})[0])
        self.assertFalse(contradicts({"origin_country_code": "NO", "dest_country_code": "SG"})[0])


class UntouchedMovePlanTests(unittest.TestCase):
    """Arm B — clears the 779 rows that have no route data to contradict."""

    def test_a_bare_default_move_plan_is_untouched(self):
        profile = json.dumps({"movePlan": {"origin": INVENTED_ORIGIN,
                                           "destination": INVENTED_DESTINATION}})
        self.assertTrue(is_untouched_move_plan(profile))

    def test_any_real_field_makes_it_touched(self):
        """Each of these is a user actually filling the form in — the pair may be theirs."""
        for extra in (
            {"targetArrivalDate": "2026-10-01"},
            {"shippingDatePreference": "2026-09-15"},
            {"housing": {"preferredAreas": ["Frogner"]}},
            {"housing": {"desiredMoveInDate": "2026-10-01"}},
            {"schooling": {"schoolingStartDate": "2026-08-20"}},
            {"movers": {"inventoryRough": "large"}},
            {"movers": {"specialItems": ["piano"]}},
        ):
            with self.subTest(extra=extra):
                self.assertFalse(is_untouched_move_plan(_profile(extra=extra)))

    def test_empty_collections_do_not_count_as_touched(self):
        profile = _profile(extra={"housing": {"preferredAreas": [], "mustHave": []},
                                  "movers": {"specialItems": []}})
        # _profile sets targetArrivalDate, so strip it to isolate the collections
        loaded = json.loads(profile)
        loaded["movePlan"].pop("targetArrivalDate")
        self.assertTrue(is_untouched_move_plan(json.dumps(loaded)))

    def test_survives_junk(self):
        for junk in ("", "not json", json.dumps([1, 2]), json.dumps({"movePlan": "nope"})):
            self.assertFalse(is_untouched_move_plan(junk))


class ClearKeysTests(unittest.TestCase):
    def test_clears_only_the_two_invented_keys(self):
        out = json.loads(clear_keys(_profile()))
        self.assertEqual("", out["movePlan"]["origin"])
        self.assertEqual("", out["movePlan"]["destination"])
        # everything else survives — this is real user input
        self.assertEqual("2026-10-01", out["movePlan"]["targetArrivalDate"])
        self.assertEqual(4, out["familySize"])

    def test_refuses_a_profile_whose_pair_is_not_the_invented_one(self):
        self.assertIsNone(clear_keys(_profile(origin="Paris, France")))
        self.assertIsNone(clear_keys(_profile(destination="Dublin")))

    def test_survives_junk(self):
        for junk in ("", "not json", json.dumps([1, 2]), json.dumps({"movePlan": "nope"})):
            self.assertIsNone(clear_keys(junk))


if __name__ == "__main__":
    unittest.main()
