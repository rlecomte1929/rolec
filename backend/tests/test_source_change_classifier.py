"""P2-02b · Material-vs-cosmetic source-change diff classifier (AIQ-690).

The classifier compares the old vs new text of a crawled source page and
decides whether the *rule* changed (material) or only its presentation
(cosmetic: markup, whitespace, navigation, styling, footer timestamps).

Validation criterion (from the Work Queue task): a golden fixture of 10
labelled diffs — classifier matches the label on >= 9/10.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.source_change_classifier import classify_diff

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "source_change_classifier_golden.json")


class SourceChangeClassifierGoldenTests(unittest.TestCase):
    def test_golden_fixture_matches_at_least_9_of_10(self) -> None:
        with open(_FIXTURE, encoding="utf-8") as fh:
            cases = json.load(fh)["cases"]
        self.assertEqual(len(cases), 10, "golden fixture must hold exactly 10 cases")

        mismatches = []
        for case in cases:
            result = classify_diff(case["old"], case["new"])
            predicted = "material" if result.is_material else "cosmetic"
            if predicted != case["label"]:
                mismatches.append(f"{case['id']}: expected {case['label']}, got {predicted}")

        matched = len(cases) - len(mismatches)
        self.assertGreaterEqual(
            matched, 9, f"classifier matched {matched}/10; mismatches: {mismatches}"
        )


class SourceChangeClassifierUnitTests(unittest.TestCase):
    def test_block_tag_wrapper_only_is_not_material(self) -> None:
        # Same visible text, only the wrapping tag changed.
        r = classify_diff("<p>The fee is CHF 100.</p>", "<div>The fee is CHF 100.</div>")
        self.assertFalse(r.is_material)
        self.assertEqual(r.changed_sections, [])

    def test_whitespace_only_is_not_material(self) -> None:
        r = classify_diff("Apply    within\n  14 days.", "Apply within 14 days.")
        self.assertFalse(r.is_material)

    def test_fee_change_is_material_with_fee_category(self) -> None:
        r = classify_diff("<p>Fee is CHF 100.</p>", "<p>Fee is CHF 140.</p>")
        self.assertTrue(r.is_material)
        self.assertIn("fee", [s.category for s in r.changed_sections])

    def test_footer_timestamp_bump_is_not_material(self) -> None:
        r = classify_diff(
            "<footer>Last updated: January 3, 2026</footer>",
            "<footer>Last updated: January 5, 2026</footer>",
        )
        self.assertFalse(r.is_material)

    def test_new_page_with_fee_is_material(self) -> None:
        r = classify_diff("", "<p>The application fee is EUR 250.</p>")
        self.assertTrue(r.is_material)
        self.assertTrue(len(r.changed_sections) >= 1)

    def test_to_dict_shape(self) -> None:
        r = classify_diff("<p>Fee is CHF 100.</p>", "<p>Fee is CHF 140.</p>")
        d = r.to_dict()
        self.assertIn("is_material", d)
        self.assertIn("changed_sections", d)
        self.assertIsInstance(d["changed_sections"], list)
        self.assertIn("category", d["changed_sections"][0])
        self.assertIn("kind", d["changed_sections"][0])
        self.assertIn("text", d["changed_sections"][0])


if __name__ == "__main__":
    unittest.main()
