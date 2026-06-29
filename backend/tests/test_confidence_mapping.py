"""AIQ-806 · Unit tests for the shared source-tier → confidence mapping.

Pins the single source of truth used by both roadmap surfaces so the two paths
can never drift. Fixture-free, no DB.
"""
from __future__ import annotations

import unittest

from backend.app.services.confidence_mapping import tier_to_confidence


class TierToConfidenceTests(unittest.TestCase):
    def test_known_tiers_str(self):
        self.assertEqual(tier_to_confidence("1"), "HIGH")
        self.assertEqual(tier_to_confidence("2"), "MEDIUM")
        self.assertEqual(tier_to_confidence("3"), "LOW")

    def test_known_tiers_int(self):
        # corpus JSON carries tier as an int; source_pages stores it as TEXT.
        self.assertEqual(tier_to_confidence(1), "HIGH")
        self.assertEqual(tier_to_confidence(2), "MEDIUM")
        self.assertEqual(tier_to_confidence(3), "LOW")

    def test_float_coerces(self):
        self.assertEqual(tier_to_confidence(2.0), "MEDIUM")

    def test_whitespace_tolerated(self):
        self.assertEqual(tier_to_confidence(" 1 "), "HIGH")

    def test_unknown_is_honest(self):
        # Missing / unrecognised never fabricates confidence.
        self.assertEqual(tier_to_confidence(None), "UNKNOWN")
        self.assertEqual(tier_to_confidence(""), "UNKNOWN")
        self.assertEqual(tier_to_confidence("9"), "UNKNOWN")
        self.assertEqual(tier_to_confidence(0), "UNKNOWN")
        self.assertEqual(tier_to_confidence("tier-1"), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
