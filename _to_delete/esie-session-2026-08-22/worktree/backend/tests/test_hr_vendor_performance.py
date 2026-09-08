"""
[NAV-SP-2] Unit tests for the HR Vendor Performance classifiers.

Pure-function coverage for the two thresholds that drive the dashboard:
  - _coverage_status: heatmap cell (healthy / thin / gap)
  - _health_status:   per-category roster status

Full endpoint shape (coverage[] aggregation, company scoping) is exercised by
the integration suite; these guard the boundary thresholds cheaply.
"""
from __future__ import annotations

import os
import sys
import unittest

# ── Repo root on sys.path ────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.app.routers.hr_vendor_performance import (  # noqa: E402
    _coverage_status,
    _health_status,
)


class CoverageStatusTests(unittest.TestCase):
    def test_gap_at_zero(self):
        self.assertEqual(_coverage_status(0), "gap")

    def test_thin_one_and_two(self):
        self.assertEqual(_coverage_status(1), "thin")
        self.assertEqual(_coverage_status(2), "thin")

    def test_healthy_three_plus(self):
        self.assertEqual(_coverage_status(3), "healthy")
        self.assertEqual(_coverage_status(9), "healthy")

    def test_negative_is_gap(self):
        # Defensive: counts should never be negative, but classify as gap.
        self.assertEqual(_coverage_status(-1), "gap")


class HealthStatusTests(unittest.TestCase):
    def test_single_vendor_is_critical(self):
        self.assertEqual(_health_status(1, 4.9), "critical")
        self.assertEqual(_health_status(0, None), "critical")

    def test_two_vendors_is_low_coverage(self):
        self.assertEqual(_health_status(2, 4.9), "low_coverage")

    def test_low_rating_triggers_review(self):
        self.assertEqual(_health_status(5, 3.5), "review")

    def test_healthy_when_enough_vendors_and_good_rating(self):
        self.assertEqual(_health_status(5, 4.2), "healthy")

    def test_rating_at_threshold_is_healthy(self):
        # 3.8 is the boundary: < 3.8 is review, == 3.8 is healthy.
        self.assertEqual(_health_status(5, 3.8), "healthy")

    def test_missing_rating_is_healthy_with_coverage(self):
        self.assertEqual(_health_status(4, None), "healthy")


if __name__ == "__main__":
    unittest.main()
