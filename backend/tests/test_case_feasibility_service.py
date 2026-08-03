"""AIQ-1749 — the app-layer bridge that resolves a case's corridor feasibility.

Covers the resolution + every fallback path without mounting the FastAPI app, so it
runs against the real corridor registry with no web stack. The router-level shape
(the nullable block on GET /overview) is covered by test_hr_case_detail_feasibility.
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
from backend.app.services.case_feasibility import feasibility_for_case  # noqa: E402

_TODAY = date(2026, 8, 3)


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def _at(self, origin, dest, days_out, start=None):
        target = start if start is not None else _TODAY + timedelta(days=days_out)
        return feasibility_for_case(origin, dest, target, today=_TODAY)

    def test_es_ie_short_notice_is_critical(self):
        result = self._at("ES", "IE", 30)
        self.assertIsNotNone(result)
        self.assertEqual(result.verdict, "critical")
        self.assertEqual(result.required_days, 104)
        self.assertEqual(result.available_days, 30)

    def test_es_ie_comfortable_horizon_is_ok(self):
        self.assertEqual(self._at("ES", "IE", 300).verdict, "ok")

    def test_free_movement_never_warns(self):
        for origin, dest in (
            ("FR", "NO"), ("ES", "NL"), ("DE", "NO"), ("FR", "CH"),
            ("FR", "DE"), ("FR", "ES"), ("FR", "NL"), ("NO", "FR"),
        ):
            for days_out in (0, 7, 30, 90):
                self.assertEqual(
                    self._at(origin, dest, days_out).verdict, "ok",
                    f"{origin}->{dest} warned at {days_out}d out",
                )

    def test_in_de_bluecard_is_covered_too(self):
        self.assertEqual(self._at("IN", "DE", 90).verdict, "critical")

    def test_accepts_a_string_date_as_the_db_returns_it(self):
        result = self._at("ES", "IE", 0, start="2026-09-02")  # 30 days after _TODAY
        self.assertIsNotNone(result)
        self.assertEqual(result.available_days, 30)

    def test_accepts_a_timestamp_string(self):
        result = self._at("ES", "IE", 0, start="2026-09-02 00:00:00+00")
        self.assertIsNotNone(result)
        self.assertEqual(result.available_days, 30)


class NeverRaisesTests(unittest.TestCase):
    """Every failure path degrades to None. The cockpit must not 500."""

    def setUp(self):
        reg._reset_cache_for_tests()
        self.addCleanup(reg._reset_cache_for_tests)

    def test_none_for_missing_inputs(self):
        for args in (
            (None, "IE", _TODAY),
            ("ES", None, _TODAY),
            ("ES", "IE", None),
            (None, None, None),
            ("", "", _TODAY),
        ):
            self.assertIsNone(feasibility_for_case(*args, today=_TODAY))

    def test_none_for_unknown_corridor(self):
        self.assertIsNone(feasibility_for_case("ZZ", "QQ", _TODAY, today=_TODAY))

    def test_none_for_unparseable_date(self):
        for bad in ("not-a-date", "2026-13-45", "   ", 12345):
            self.assertIsNone(feasibility_for_case("ES", "IE", bad, today=_TODAY))

    def test_never_raises_on_a_broken_registry(self):
        # Simulate the registry blowing up mid-resolution.
        from unittest.mock import patch
        with patch.object(reg, "get_pathways", side_effect=RuntimeError("boom")):
            self.assertIsNone(feasibility_for_case("ES", "IE", _TODAY, today=_TODAY))

    def test_absent_opinion_is_none_not_ok(self):
        # The critical contract: an unresolvable corridor must NOT come back as a
        # reassuring "ok" verdict, because the UI renders ok as "no problem".
        result = feasibility_for_case("ZZ", "QQ", _TODAY, today=_TODAY)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
