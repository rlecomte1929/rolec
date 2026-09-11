"""Pre-departure track — the home-country obligations closed before leaving.

The front half of the round-trip and the mirror of test_return_track_roadmap. A
same-country move has no home to leave. For NO→FR the authored Norwegian exit steps
(Folkeregister, folketrygden, BankID) must land in this track, not in Settlement —
that is the bug this build fixes: they were defaulting to the settlement track and
rendering under "settle in France".
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.roadmap_builder import derive_roadmap


def _case(origin="ES", dest="IE", nationality=None, marital="solo"):
    return {
        "id": "case-predep",
        "status": "open",
        "draft": {
            "relocationBasics": {"originCountry": origin, "destCountry": dest, "destCity": "City"},
            "employeeProfile": {"nationality": nationality, "fullName": "Test Mover"},
            "familyMembers": {"maritalStatus": marital},
        },
    }


def _predep(result):
    return next((t for t in result["tracks"] if t["id"] == "predeparture"), None)


def _corridor_keys(track):
    return {s["key"] for s in track.get("steps", []) if str(s["key"]).startswith("corridor-")}


class PredepartureTrackTests(unittest.TestCase):
    def test_cross_border_move_gets_a_predeparture_track_first(self) -> None:
        result = derive_roadmap(_case(origin="ES", dest="IE"))
        track = _predep(result)
        self.assertIsNotNone(track, "pre-departure track missing")
        self.assertEqual(track["name"], "Pre-departure")
        self.assertEqual(
            result["tracks"][0]["id"], "predeparture", "pre-departure must come first in the arc"
        )
        self.assertIn("Home-country obligations closed", result["outcomes"])

    def test_same_country_move_has_no_predeparture_track(self) -> None:
        result = derive_roadmap(_case(origin="DE", dest="DE"))
        self.assertIsNone(_predep(result))
        self.assertNotIn("Home-country obligations closed", result["outcomes"])

    def test_missing_origin_keeps_the_track_fail_open(self) -> None:
        result = derive_roadmap({"id": "c", "status": "open", "draft": {}})
        self.assertIsNotNone(_predep(result))

    def test_skeleton_steps_follow_the_step_schema(self) -> None:
        # A pair with no authored corridor, so the track is the pure generic skeleton.
        track = _predep(derive_roadmap(_case(origin="US", dest="BR")))
        self.assertTrue(track["steps"])
        required = {"n", "key", "title", "status", "owner", "where", "time", "cost", "depends", "line", "subs"}
        for step in track["steps"]:
            self.assertTrue(required.issubset(step.keys()), f"missing keys in {step.get('key')}")
            self.assertEqual(step["status"], "locked")
        keys = {s["key"] for s in track["steps"]}
        self.assertTrue(
            {"predep-review", "predep-tax", "predep-deregister", "predep-social", "predep-financial"}.issubset(keys)
        )

    def test_no_fr_exit_steps_route_into_predeparture_not_settlement(self) -> None:
        result = derive_roadmap(_case(origin="NO", dest="FR", nationality="FR"))
        predep = _predep(result)
        self.assertIsNotNone(predep, "NO→FR must have a pre-departure track")
        predep_corridor = _corridor_keys(predep)
        # Authored Norwegian exit steps land in the pre-departure track…
        for key in ("corridor-a1_folkeregister", "corridor-a5_folketrygden_exit", "corridor-a2_preserve_bankid"):
            self.assertIn(key, predep_corridor, f"{key} should be in the pre-departure track")
        # …and not misrouted into settlement.
        settlement = next((t for t in result["tracks"] if t["id"] == "settlement"), None)
        self.assertIsNotNone(settlement)
        settle_keys = {s["key"] for s in settlement.get("steps", [])}
        self.assertNotIn("corridor-a5_folketrygden_exit", settle_keys)
        # Authored steps supersede the generic placeholders they detail; the planning step stays.
        generic_keys = {s["key"] for s in predep["steps"] if not str(s["key"]).startswith("corridor-")}
        self.assertNotIn("predep-deregister", generic_keys, "A1 should supersede the generic de-register placeholder")
        self.assertIn("predep-review", generic_keys, "the planning step is never superseded")


def _dep_req(id, title, desc="Do the thing.", non_obvious=True, pillar="IDENTITY", timing=None):
    return {"id": id, "pillar": pillar, "title": title, "description": desc, "non_obvious": non_obvious, "timing": timing}


class DepartureRequirementsInjectionTests(unittest.TestCase):
    """derive_roadmap(..., departure_requirements=...) — the Andrea (ES→IE) content path.

    Uses fixtures, so it exercises the injection without a DB (the DB read lives in the
    endpoints, not derive_roadmap).
    """

    def test_origin_requirements_supersede_generic_and_appear(self) -> None:
        reqs = [
            _dep_req("es-baja-padron", "Baja del padrón"),
            _dep_req("es-aeat-exit", "AEAT tax exit", non_obvious=False, pillar="EMPLOYMENT"),
        ]
        predep = _predep(derive_roadmap(_case(origin="ES", dest="IE"), departure_requirements=reqs))
        keys = {s["key"] for s in predep["steps"]}
        self.assertIn("origin-req-es-baja-padron", keys)
        self.assertIn("origin-req-es-aeat-exit", keys)
        for gone in ("predep-tax", "predep-deregister", "predep-social", "predep-financial"):
            self.assertNotIn(gone, keys, f"{gone} placeholder should be superseded by real requirements")
        self.assertIn("predep-review", keys, "the planning step is never superseded")
        baja = next(s for s in predep["steps"] if s["key"] == "origin-req-es-baja-padron")
        self.assertTrue(baja["nonObvious"])
        self.assertEqual(baja["status"], "locked")
        self.assertEqual(baja["owner"], "You")

    def test_pathway_authored_exit_steps_win_over_requirement_items(self) -> None:
        # NO→FR authors its own exit steps; injected requirement_items must not double-serve.
        reqs = [_dep_req("no-folkereg", "Report move to Folkeregisteret")]
        predep = _predep(derive_roadmap(_case(origin="NO", dest="FR", nationality="FR"), departure_requirements=reqs))
        keys = {s["key"] for s in predep["steps"]}
        self.assertNotIn("origin-req-no-folkereg", keys, "pathway wins; requirement_items skipped")
        self.assertIn("corridor-a1_folkeregister", keys, "authored pathway steps remain")

    def test_no_departure_requirements_keeps_generic_skeleton(self) -> None:
        for reqs in (None, []):
            keys = {s["key"] for s in _predep(derive_roadmap(_case(origin="ES", dest="IE"), departure_requirements=reqs))["steps"]}
            self.assertIn("predep-tax", keys)
            self.assertIn("predep-deregister", keys)


if __name__ == "__main__":
    unittest.main()
