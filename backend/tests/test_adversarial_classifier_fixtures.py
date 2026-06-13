"""
test_adversarial_classifier_fixtures.py — AIQ-588 / AI-W4.2

Validates the hand-crafted adversarial classifier fixtures
(backend/tests/fixtures/adversarial/classifier/*.json) for schema integrity and
internal consistency. Pure-Python unittest — no LLM call, no network. This guards
the deliverable against the phantom failure mode (files silently absent/malformed)
and machine-checks the task's validation criteria:

    "All 5 fixtures committed. Classifier failure modes documented.
     At least 2 of the 5 escalate to GPT-4o per the threshold."

The GPT-4o escalation threshold for document_classification is 0.80
(backend/relopass/llm/router.py — ESCALATION_CONFIDENCE_THRESHOLDS), so a fixture
escalates iff its expected confidence band tops out below 0.80.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "adversarial" / "classifier"
_ESCALATION_THRESHOLD = 0.80

_REQUIRED_KEYS = {
    "fixture_id",
    "fixture_name",
    "adversarial_category",
    "expected_label",
    "expected_confidence_band",
    "escalation_to_gpt4o_expected",
    "document_text",
    "why_adversarial",
    "classifier_failure_mode",
    "gold_signals_expected",
    "notes",
}


def _load_fixtures():
    return sorted(_FIXTURE_DIR.glob("*.json"))


class TestAdversarialClassifierFixtures(unittest.TestCase):
    def test_exactly_five_fixtures_committed(self):
        files = _load_fixtures()
        self.assertEqual(len(files), 5, f"expected 5 fixtures, found {[f.name for f in files]}")

    def test_notes_documenting_failure_modes_present(self):
        self.assertTrue((_FIXTURE_DIR / "notes.md").is_file(), "notes.md (failure-mode docs) missing")

    def test_each_fixture_valid_schema(self):
        for f in _load_fixtures():
            with self.subTest(fixture=f.name):
                d = json.loads(f.read_text())
                self.assertEqual(_REQUIRED_KEYS - set(d), set(), f"{f.name} missing keys")
                band = d["expected_confidence_band"]
                self.assertEqual(len(band), 2)
                self.assertLessEqual(band[0], band[1])
                self.assertTrue(0.0 <= band[0] <= 1.0 and 0.0 <= band[1] <= 1.0)
                self.assertTrue(d["document_text"].strip(), "document_text empty")
                self.assertLessEqual(len(d["document_text"]), 8000, "document_text exceeds 8000-char classifier limit")
                self.assertTrue(2 <= len(d["gold_signals_expected"]) <= 4, "expect 2-4 gold signals")

    def test_escalation_flag_consistent_with_band(self):
        """escalation_to_gpt4o_expected must equal (band high < 0.80)."""
        for f in _load_fixtures():
            with self.subTest(fixture=f.name):
                d = json.loads(f.read_text())
                band_high = d["expected_confidence_band"][1]
                self.assertEqual(
                    d["escalation_to_gpt4o_expected"],
                    band_high < _ESCALATION_THRESHOLD,
                    f"{d['fixture_id']}: escalation flag inconsistent with band {d['expected_confidence_band']}",
                )

    def test_at_least_two_fixtures_escalate(self):
        escalating = sum(
            1 for f in _load_fixtures() if json.loads(f.read_text())["escalation_to_gpt4o_expected"]
        )
        self.assertGreaterEqual(escalating, 2, "validation criterion: >=2 of 5 must escalate to GPT-4o")

    def test_fixture_ids_unique(self):
        ids = [json.loads(f.read_text())["fixture_id"] for f in _load_fixtures()]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate fixture_id: {ids}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
