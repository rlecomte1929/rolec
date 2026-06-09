"""[AIQ-672 / AI-I.3c] EU passport recognizer tests.

Validation criterion: a 100-example fixture across FR/DE/NO/IT passports with
recall >= 95 % and false-positive rate <= 1 %. The fixture exercises the pure
detector (`find_passports`) so it runs without the presidio/spaCy ML stack.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from backend.app.services.pii.presidio_recognizers import eu_passport as ep

_DE_FIRST = "CDEFGHJKLMNPRTVWXYZ"
_ALNUM = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _fr(i: int) -> str:
    return f"{(i % 90) + 10:02d}{chr(65 + i % 26)}{chr(65 + (i * 3) % 26)}{(i * 137) % 100000:05d}"


def _it(i: int) -> str:
    return f"{chr(65 + i % 26)}{chr(65 + (i * 5) % 26)}{(i * 9173) % 10000000:07d}"


def _de(i: int) -> str:
    tail = "".join(_ALNUM[(i * (k + 3)) % len(_ALNUM)] for k in range(8))
    return f"{_DE_FIRST[i % len(_DE_FIRST)]}{tail}"


def _no(i: int) -> str:
    return f"{(i * 7919) % 100000000:08d}"


def _build_positives():
    """100 realistic snippets (25 per country) with natural keyword context."""
    pos = []
    for i in range(25):
        pos.append(("FR", f"Passeport n {_fr(i)} delivre a Paris"))
        pos.append(("IT", f"Passaporto {_it(i)} rilasciato"))
        pos.append(("DE", f"Reisepass {_de(i)} ausgestellt in Berlin"))
        pos.append(("NO", f"Passnummer {_no(i)} utstedt"))
    return pos


def _build_negatives():
    """100 hard negatives with NO passport keyword and no FR/IT/MRZ shape."""
    neg = []
    ibans = [
        "DE89370400440532013000", "FR1420041010050500013M02606",
        "NO9386011117947", "IT60X0542811101000000123456",
        "GB29NWBK60161331926819", "ES9121000418450200051332",
    ]
    for k in range(20):
        neg.append(ibans[k % len(ibans)])
    for k in range(20):
        neg.append(f"+47 {(k * 13 % 90) + 10:02d} {(k * 7) % 100:02d} {(k * 11) % 100:02d} {(k * 5) % 100:02d}")
    for k in range(20):
        neg.append(f"Invoice date 2026-{(k % 12) + 1:02d}-{(k % 27) + 1:02d}")
    for k in range(20):
        neg.append(f"Order {(k * 524287) % 100000000:08d} shipped")  # 8 digits, no keyword
    extras = [
        "Total: 1234.56 EUR", "Building 42, Floor 7", "SKU ABCD12345",
        "Ref 123456789 approved", "Room 101 at 09:30", "Tax year 2025-2026",
        "Lot 7788 batch 991", "Temperature 36.6 C", "Version 4.6.1 release",
        "Coordinates 59.91, 10.75", "Price was 9 990 NOK total",
        "Customer since 2019 loyal", "Ticket ABC-99213 open",
        "Distance 12 km approx", "Meeting at 14:00 sharp",
        "Account balance 4521 kr", "Page 7 of 12 read", "Box 3344 storage",
        "Flight DY1234 boarding", "Gate B17 departure",
    ]
    for k in range(20):
        neg.append(extras[k % len(extras)])
    return neg


class TestRecallAndFalsePositive(unittest.TestCase):
    def test_recall_at_least_95pct(self):
        pos = _build_positives()
        self.assertEqual(len(pos), 100)
        detected = sum(1 for _, snip in pos if ep.find_passports(snip))
        recall = detected / len(pos)
        missed = [snip for _, snip in pos if not ep.find_passports(snip)]
        self.assertGreaterEqual(recall, 0.95, f"recall={recall:.3f}; missed={missed[:5]}")

    def test_false_positive_at_most_1pct(self):
        neg = _build_negatives()
        self.assertEqual(len(neg), 100)
        flagged = [s for s in neg if ep.find_passports(s)]
        fp_rate = len(flagged) / len(neg)
        self.assertLessEqual(fp_rate, 0.01, f"fp_rate={fp_rate:.3f}; flagged={flagged[:5]}")


class TestCheckDigit(unittest.TestCase):
    def test_valid_mrz_document_number(self):
        # ICAO 9303 example: compute_check_digit("L898902C3") == 6
        self.assertTrue(ep.is_valid_mrz_document_number("L898902C36"))

    def test_wrong_check_digit_rejected(self):
        self.assertFalse(ep.is_valid_mrz_document_number("L898902C30"))

    def test_bad_shape_rejected(self):
        self.assertFalse(ep.is_valid_mrz_document_number("short"))
        self.assertFalse(ep.is_valid_mrz_document_number("L898902C3X"))  # last not a digit

    def test_mrz_token_detected_anywhere(self):
        # No passport keyword — checksum alone carries it.
        matches = ep.find_passports("doc field L898902C36 in the scan")
        self.assertTrue(any(m.country == "MRZ" for m in matches))


class TestContextGating(unittest.TestCase):
    def test_bare_8_digits_not_flagged_without_context(self):
        self.assertEqual(ep.find_passports("the order 12345678 was shipped"), [])

    def test_8_digits_flagged_with_passport_context(self):
        self.assertTrue(ep.find_passports("Passport 12345678 issued"))

    def test_fr_format_strong_without_context(self):
        self.assertTrue(ep.find_passports("number 19AB54321 noted"))

    def test_password_does_not_trigger(self):
        # "password" must NOT count as passport context for the 8-digit shape.
        self.assertEqual(ep.find_passports("your password 12345678 here"), [])


class TestPresidioRecognizer(unittest.TestCase):
    def test_get_recognizers(self):
        try:
            recs = ep.get_recognizers()
        except ImportError:
            self.skipTest("presidio-analyzer not installed in this env")
        self.assertEqual(len(recs), 1)
        self.assertIn(ep.PASSPORT_ENTITY, recs[0].get_supported_entities())


if __name__ == "__main__":
    unittest.main()
