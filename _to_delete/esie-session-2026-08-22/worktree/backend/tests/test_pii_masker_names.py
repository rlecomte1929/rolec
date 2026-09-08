"""
AI-I.3f-FU — person-name masking in pii_masker (pure-Python path).

These tests pin the behaviour added on top of the AI-I.3f checksum wiring:
``mask_pii`` now redacts person names (FR/DE/NO/Hindi, context-boosted) as a
fail-soft ``[REDACTED_PERSON]`` pass via ``multilingual_names.find_names`` — with
NO presidio/spaCy dependency. The suite asserts:

  1. Recall >= 0.90 over a multilingual fixture (the task's acceptance bar).
  2. The path works with presidio ABSENT (the real env here) and never raises.
  3. Names compose with the existing PII rules + stay idempotent.
  4. No over-masking of benign capitalised prose (regression guard).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.pii_masker import mask_pii, is_already_masked  # noqa: E402

# (prompt, the name substring that must NOT survive) — FR / DE / NO / Hindi / EN,
# each carrying the honorific / birth-cue / Devanagari context find_names keys on.
_NAME_FIXTURE = [
    ("Veuillez contacter M. Jean Dupont demain.", "Jean Dupont"),          # FR honorific
    ("L'employée, née Marie Lefebvre, arrive lundi.", "Marie Lefebvre"),    # FR birth cue
    ("Bitte wenden Sie sich an Herr Klaus Müller.", "Klaus Müller"),        # DE honorific
    ("Die Person, geboren als Hans Schmidt, zieht um.", "Hans Schmidt"),    # DE birth cue
    ("Kontakt herr Lars Hansen for detaljer.", "Lars Hansen"),              # NO honorific
    ("Personen, født Erik Olsen, flytter snart.", "Erik Olsen"),            # NO birth cue
    ("Fullt navn: Ingrid Bakke.", "Ingrid Bakke"),                          # NO name cue
    ("कृपया श्री राज कुमार से संपर्क करें।", "राज कुमार"),                          # Hindi honorific + Devanagari
    ("उनका नाम प्रिया शर्मा है।", "प्रिया शर्मा"),                                 # Hindi Devanagari
    ("Please contact Dr Alan Turing about the case.", "Alan Turing"),       # EN honorific
]


class PiiMaskerNameTests(unittest.TestCase):

    def test_presidio_and_spacy_are_absent(self) -> None:
        # The whole point of the pure-Python path: name masking works without
        # the heavyweight ML stack. If this assumption ever changes, the
        # recall numbers below are measuring something different.
        self.assertIsNone(importlib.util.find_spec("presidio_analyzer"))
        self.assertIsNone(importlib.util.find_spec("spacy"))

    def test_multilingual_name_recall_at_least_090(self) -> None:
        masked_ok = 0
        misses = []
        for prompt, name in _NAME_FIXTURE:
            out = mask_pii(prompt)
            if name not in out and "[REDACTED_PERSON]" in out:
                masked_ok += 1
            else:
                misses.append((prompt, out))
        recall = masked_ok / len(_NAME_FIXTURE)
        self.assertGreaterEqual(
            recall, 0.90,
            msg=f"name-mask recall {recall:.2f} < 0.90; misses={misses}",
        )

    def test_each_language_family_masks_at_least_one(self) -> None:
        # Guard against a recall number propped up by one language.
        families = {
            "FR": _NAME_FIXTURE[0:2],
            "DE": _NAME_FIXTURE[2:4],
            "NO": _NAME_FIXTURE[4:7],
            "Hindi": _NAME_FIXTURE[7:9],
        }
        for fam, cases in families.items():
            hit = any(
                name not in mask_pii(prompt) and "[REDACTED_PERSON]" in mask_pii(prompt)
                for prompt, name in cases
            )
            self.assertTrue(hit, msg=f"no name masked for language family {fam}")

    def test_name_masking_never_raises_on_weird_input(self) -> None:
        for bad in ["", "M.", "श्री", "né", "Herr", "\x00\x01", "Mr " * 50]:
            self.assertIsInstance(mask_pii(bad), str)

    def test_name_composes_with_other_pii(self) -> None:
        out = mask_pii("Contact M. Jean Dupont at +33 6 12 34 56 78 or jd@example.com")
        self.assertIn("[REDACTED_PERSON]", out)
        self.assertIn("[REDACTED_PHONE]", out)
        self.assertIn("[REDACTED_EMAIL]", out)
        self.assertNotIn("Jean Dupont", out)

    def test_name_masking_is_idempotent(self) -> None:
        text = "Please contact Dr Alan Turing at +33612345678"
        once = mask_pii(text)
        twice = mask_pii(once)
        self.assertEqual(once, twice)
        self.assertTrue(is_already_masked(once))

    def test_benign_capitalised_prose_not_over_masked(self) -> None:
        # No honorific / birth cue / Devanagari → the booster stays quiet, so
        # ordinary product copy is left intact.
        for benign in [
            "What is the housing allowance for managers?",
            "The Long Term Assignment policy covers temporary housing.",
            "Send the report to the London office by Friday.",
        ]:
            self.assertNotIn("[REDACTED_PERSON]", mask_pii(benign))


if __name__ == "__main__":
    unittest.main()
