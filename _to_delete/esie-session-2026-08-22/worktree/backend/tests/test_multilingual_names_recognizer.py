"""[AIQ-674 / AI-I.3e] Multilingual name recognizer tests.

Validation criterion: a 100-example multilingual fixture with recall ≥ 0.90,
false-positive ≤ 1 %, and cross-language FP ≤ 1 %. The fixture exercises the
pure detector (`find_names`) so it runs without the presidio/spaCy ML stack.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from backend.app.services.pii.presidio_recognizers import multilingual_names as mn

_FR = [("Jean", "Dupont"), ("Marie", "Lefèvre"), ("Pierre", "Martin"),
       ("Sophie", "Bernard"), ("Luc", "Moreau")]
_DE = [("Hans", "Müller"), ("Anna", "Schmidt"), ("Lukas", "Schäfer"),
       ("Greta", "Weiß"), ("Jonas", "Böhm")]
_NO = [("Kari", "Nordmann"), ("Ola", "Hansen"), ("Ingrid", "Solberg"),
       ("Erik", "Bakke"), ("Astrid", "Lie")]
_HI = ["राहुल शर्मा", "प्रिया सिंह", "अमित कुमार", "सुनीता देवी", "विक्रम पटेल"]


def _build_positives():
    """100 snippets (25 per FR/DE/NO/Hindi), each with a language context cue."""
    pos = []
    for i in range(25):
        gf = _FR[i % len(_FR)]
        pos.append(("FR", (f"M. {gf[0]} {gf[1]}" if i % 2 else f"née le 03/1990, {gf[0]} {gf[1]}")))
        gd = _DE[i % len(_DE)]
        pos.append(("DE", (f"Herr {gd[0]} {gd[1]}" if i % 2 else f"geboren {gd[0]} {gd[1]} in 1988")))
        gn = _NO[i % len(_NO)]
        pos.append(("NO", (f"Navn: {gn[0]} {gn[1]}" if i % 2 else f"født {gn[0]} {gn[1]}")))
        hi = _HI[i % len(_HI)]
        pos.append(("HI", f"श्री {hi}"))
    return pos


def _build_negatives():
    """100 hard negatives: capitalised words/places/cross-language traps, no name."""
    neg = [
        "The Quarterly Report is due Friday.",
        "Visit New York City next spring.",
        "United Nations summit opens Monday.",
        "The Project Manager approved the budget.",
        "Our Berlin office expands this year.",
        "Machine Learning models improved.",
        "The European Union released a statement.",
        "Open Source software powers it.",
        "World Health Organization data shows trends.",
        "Customer Success team grew.",
        # cross-language traps: cue/honorific present but the capitalised run is a PLACE
        "geboren in München am Dienstag",
        "geboren in Bad Homburg vor der Höhe",
        "né à Lyon Centre la nuit",
        "født i Oslo sentrum",
        "The name of the river is Rhine",
        "born in San Francisco that year",
        "navn på byen er Bergen Sentrum",
        "nom de la ville: Paris Nord",
        "geboren in New Delhi spät",
        "name of the building: Empire State",
    ]
    # Pad to 100 with deterministic capitalised non-name sentences.
    cities = ["Madrid", "Vienna", "Lisbon", "Dublin", "Prague", "Athens",
              "Warsaw", "Helsinki", "Zurich", "Brussels"]
    topics = ["Annual Review", "Sales Pipeline", "Risk Committee", "Data Lake",
              "Cloud Platform", "Design System", "Growth Team", "Audit Trail"]
    i = 0
    while len(neg) < 100:
        c = cities[i % len(cities)]
        t = topics[i % len(topics)]
        neg.append(f"The {t} meeting happens in {c} next week.")
        i += 1
    return neg[:100]


class TestRecallAndFalsePositive(unittest.TestCase):
    def test_recall_at_least_90pct(self):
        pos = _build_positives()
        self.assertEqual(len(pos), 100)
        detected = sum(1 for _, snip in pos if mn.find_names(snip))
        recall = detected / len(pos)
        missed = [snip for _, snip in pos if not mn.find_names(snip)]
        self.assertGreaterEqual(recall, 0.90, f"recall={recall:.3f}; missed={missed[:5]}")

    def test_false_positive_at_most_1pct(self):
        neg = _build_negatives()
        self.assertEqual(len(neg), 100)
        flagged = [s for s in neg if mn.find_names(s)]
        fp_rate = len(flagged) / len(neg)
        self.assertLessEqual(fp_rate, 0.01, f"fp_rate={fp_rate:.3f}; flagged={flagged[:5]}")

    def test_cross_language_place_after_cue_not_flagged(self):
        # A place introduced by a preposition after a birth cue is not a person.
        for s in ["geboren in Bad Homburg", "né à Lyon Centre", "født i Oslo Sentrum"]:
            self.assertEqual(mn.find_names(s), [], f"false positive on: {s}")


class TestPerLanguage(unittest.TestCase):
    def test_fr_honorific(self):
        self.assertTrue(mn.find_names("Contact M. Jean Dupont demain"))

    def test_de_birth_cue(self):
        self.assertTrue(mn.find_names("geboren Hans Müller in Köln"))

    def test_no_navn_cue(self):
        self.assertTrue(mn.find_names("Navn: Kari Nordmann"))

    def test_devanagari_name(self):
        m = mn.find_names("श्री राहुल शर्मा")
        self.assertTrue(any(x.kind == "devanagari" for x in m))

    def test_bare_caps_without_cue_not_flagged(self):
        # No cue/honorific → left to NER, not flagged by this booster module.
        self.assertEqual(mn.find_names("New York Times reported it"), [])

    def test_m_theory_not_a_name(self):
        self.assertEqual(mn.find_names("M Theory unifies strings"), [])


class TestPresidioRecognizers(unittest.TestCase):
    def test_get_recognizers(self):
        try:
            recs = mn.get_recognizers()
        except ImportError:
            self.skipTest("presidio-analyzer not installed in this env")
        self.assertEqual(len(recs), 2)
        for r in recs:
            self.assertIn(mn.PERSON_ENTITY, r.get_supported_entities())


if __name__ == "__main__":
    unittest.main()
