"""AIQ-1748 — pre-arrival runway + case-level feasibility verdict.

These tests load the REAL committed pathway YAMLs rather than hand-built fixtures.
That is deliberate: the point of deriving the threshold from the step graph is that
it tracks the corridor content, so the tests must break if a corridor's durations
drift. A fixture-based test would keep passing while the product went wrong.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date, timedelta

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import corridor_registry as reg  # noqa: E402
from backend.relopass.corridors import load_corridor  # noqa: E402
from backend.relopass.corridors.feasibility import (  # noqa: E402
    CRITICAL,
    MIN_MATERIAL_LEAD_DAYS,
    OK,
    TIGHT,
    TIGHT_BUFFER_DAYS,
    arrival_anchor_step,
    assess_feasibility,
    required_lead_time_days,
)

_TODAY = date(2026, 8, 3)

# The two permit corridors, with the runway measured from their committed step
# graphs. ES_IE: JOB_OFFER_CONTRACT 14 + PERMIT_APPLICATION 35 + PERMIT_GRANTED 7
# + D_VISA_APPLICATION 40 + D_VISA_GRANTED 7 + TRAVEL 1 = 104.
_PERMIT_CORRIDORS = {"ES_IE": 104, "IN_DE": 158}

# Everything else roots at arrival, so nothing precedes it.
_FREE_MOVEMENT = ("DE_NO", "ES_NL", "FR_CH", "FR_DE", "FR_ES", "FR_NL", "FR_NO", "NO_FR")


def _steps(corridor_id):
    pathways = reg.get_pathways(corridor_id)
    assert pathways, f"{corridor_id} declares no pathways"
    path = reg.get_pathway_file(corridor_id, pathways[0].id)
    assert path is not None, f"{corridor_id}/{pathways[0].id} did not resolve"
    return load_corridor(path).step_graph


class RequiredLeadTimeTests(unittest.TestCase):
    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def test_permit_corridors_have_the_measured_runway(self):
        for corridor_id, expected in _PERMIT_CORRIDORS.items():
            self.assertEqual(
                required_lead_time_days(_steps(corridor_id)), expected,
                f"{corridor_id} pre-arrival runway changed — if a step duration was "
                f"edited on purpose (e.g. AIQ-1746), update this expectation.",
            )

    def test_free_movement_corridors_have_no_material_runway(self):
        for corridor_id in _FREE_MOVEMENT:
            runway = required_lead_time_days(_steps(corridor_id))
            self.assertLess(
                runway, MIN_MATERIAL_LEAD_DAYS,
                f"{corridor_id} measured {runway}d of pre-arrival runway; free "
                f"movement should have effectively none",
            )

    def test_permit_and_free_movement_are_not_close(self):
        # The exclusion is arithmetic, not an allowlist — so it must hold by a wide
        # margin, not by a hair.
        worst_free = max(required_lead_time_days(_steps(c)) for c in _FREE_MOVEMENT)
        best_permit = min(required_lead_time_days(_steps(c)) for c in _PERMIT_CORRIDORS)
        self.assertGreater(best_permit, worst_free * 10)

    def test_no_anchor_yields_zero(self):
        steps = tuple(s for s in _steps("ES_IE") if not s.arrival_anchor)
        self.assertIsNone(arrival_anchor_step(steps))
        self.assertEqual(required_lead_time_days(steps), 0)


class AssessFeasibilityTests(unittest.TestCase):
    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def _verdict(self, corridor_id, days_out):
        result = assess_feasibility(
            _steps(corridor_id), _TODAY + timedelta(days=days_out), _TODAY
        )
        self.assertIsNotNone(result, f"{corridor_id} returned no assessment")
        return result

    def test_es_ie_short_notice_is_critical(self):
        result = self._verdict("ES_IE", 90)
        self.assertEqual(result.verdict, CRITICAL)
        self.assertEqual(result.required_days, 104)
        self.assertEqual(result.available_days, 90)
        self.assertTrue(result.is_warning)
        self.assertIn("104", result.derivation)

    def test_es_ie_comfortable_horizon_is_ok(self):
        result = self._verdict("ES_IE", 200)
        self.assertEqual(result.verdict, OK)
        self.assertFalse(result.is_warning)

    def test_es_ie_just_enough_is_tight(self):
        # Inside the buffer above the requirement: achievable, but no slack.
        result = self._verdict("ES_IE", 104 + TIGHT_BUFFER_DAYS - 1)
        self.assertEqual(result.verdict, TIGHT)
        self.assertTrue(result.is_warning)

    def test_es_ie_boundary_exactly_meets_requirement(self):
        # Exactly the runway is not "not enough" — the boundary must not be critical.
        self.assertEqual(self._verdict("ES_IE", 104).verdict, TIGHT)
        self.assertEqual(self._verdict("ES_IE", 103).verdict, CRITICAL)

    def test_free_movement_never_warns_at_any_horizon(self):
        for corridor_id in _FREE_MOVEMENT:
            for days_out in (0, 7, 30, 90, 200):
                result = self._verdict(corridor_id, days_out)
                self.assertEqual(
                    result.verdict, OK,
                    f"{corridor_id} warned at {days_out}d out — free-movement "
                    f"corridors must never trip the feasibility warning",
                )

    def test_in_de_bluecard_inherits_the_feature(self):
        self.assertEqual(self._verdict("IN_DE", 90).verdict, CRITICAL)
        self.assertEqual(self._verdict("IN_DE", 300).verdict, OK)

    def test_no_target_date_yields_no_opinion(self):
        self.assertIsNone(assess_feasibility(_steps("ES_IE"), None, _TODAY))

    def test_no_anchor_yields_no_opinion(self):
        # An unassessable corridor must return None, never a reassuring "ok".
        steps = tuple(s for s in _steps("ES_IE") if not s.arrival_anchor)
        self.assertIsNone(assess_feasibility(steps, _TODAY + timedelta(days=1), _TODAY))

    def test_past_start_date_is_critical_for_permit_corridors(self):
        result = self._verdict("ES_IE", -10)
        self.assertEqual(result.verdict, CRITICAL)
        self.assertEqual(result.available_days, -10)


class PurityTests(unittest.TestCase):
    def test_module_does_not_import_the_app_layer(self):
        # backend/relopass/ must stay app-free: it is imported by the legacy db layer.
        import backend.relopass.corridors.feasibility as mod
        source = open(mod.__file__, encoding="utf-8").read()
        self.assertNotIn("backend.app", source)
        self.assertNotIn("from ...app", source)

    def test_today_is_injected_not_read_from_the_clock(self):
        import backend.relopass.corridors.feasibility as mod
        source = open(mod.__file__, encoding="utf-8").read()
        self.assertNotIn("date.today()", source)
        self.assertNotIn("datetime.now()", source)


if __name__ == "__main__":
    unittest.main()
