"""[AIQ-673 / AI-I.3d] National-ID recognizer tests — NO fnr, DE Steuer-ID, FR NIR.

Validation criterion: per-language fixture recall >= 95 %, FP <= 1 %. Positives
are valid by construction (built with each module's own control-digit helper);
negatives include realistic non-IDs plus "near-miss" corrupted IDs that must be
rejected by the checksum. Runs without the presidio/spaCy ML stack.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from backend.app.services.pii.presidio_recognizers import (
    no_fnr, de_steuer_id, fr_nir,
)


# ── fixture builders (valid by construction) ─────────────────────────────────
def _no_valids(n=25):
    out = []
    seed = 0
    while len(out) < n:
        seed += 1
        dd = (seed % 28) + 1
        mm = (seed % 12) + 1
        yy = (seed * 7) % 100
        ind = (seed * 137) % 1000
        first9 = f"{dd:02d}{mm:02d}{yy:02d}{ind:03d}"
        ctrl = no_fnr.fnr_control_digits(first9)
        if ctrl is None:
            continue
        out.append(f"{first9}{ctrl[0]}{ctrl[1]}")
    return out


def _de_valids(n=25):
    out = []
    for seed in range(200):
        if len(out) >= n:
            break
        base = (seed % 9) + 1  # non-zero first digit
        others = [d for d in range(10) if d != base][:8]
        # rotate others for variety; base appears exactly twice
        rot = seed % 8
        others = others[rot:] + others[:rot]
        first10 = f"{base}{base}" + "".join(str(d) for d in others)
        chk = de_steuer_id.steuer_id_check_digit(first10)
        sid = f"{first10}{chk}"
        if de_steuer_id.is_valid_steuer_id(sid):
            out.append(sid)
    return out


def _fr_valids(n=25):
    out = []
    for seed in range(1, n + 1):
        sex = "1" if seed % 2 else "2"
        yy = seed % 100
        mm = (seed % 12) + 1
        dept = (seed % 95) + 1
        commune = (seed * 13) % 1000
        order = (seed * 29) % 1000
        body = f"{sex}{yy:02d}{mm:02d}{dept:02d}{commune:03d}{order:03d}"
        key = fr_nir.nir_key(body)
        out.append(f"{body}{key:02d}")
    return out


class TestNorwegianFnr(unittest.TestCase):
    def test_recall(self):
        v = _no_valids(25)
        self.assertGreaterEqual(sum(no_fnr.is_valid_fnr(x) for x in v) / len(v), 0.95)

    def test_false_positive(self):
        valids = _no_valids(25)
        neg = ["+47 98765432", "DE89370400440532013000", "2026-06-09 12:00",
               "Order 12345678901", "00000000000", "12345678901"]
        # near-misses: corrupt the last control digit
        neg += [x[:-1] + str((int(x[-1]) + 1) % 10) for x in valids[:10]]
        fp = sum(no_fnr.is_valid_fnr(x) for x in neg) / len(neg)
        self.assertLessEqual(fp, 0.01, f"fp={fp:.3f}")

    def test_control_digits_known_property(self):
        # Flipping any control digit invalidates the number.
        v = _no_valids(1)[0]
        self.assertTrue(no_fnr.is_valid_fnr(v))
        self.assertFalse(no_fnr.is_valid_fnr(v[:10] + str((int(v[10]) + 1) % 10)))

    def test_separator_form(self):
        v = _no_valids(1)[0]
        self.assertTrue(no_fnr.is_valid_fnr(f"{v[:6]} {v[6:]}"))


class TestGermanSteuerId(unittest.TestCase):
    def test_recall(self):
        v = _de_valids(25)
        self.assertEqual(len(v), 25)
        self.assertGreaterEqual(sum(de_steuer_id.is_valid_steuer_id(x) for x in v) / len(v), 0.95)

    def test_false_positive(self):
        valids = _de_valids(25)
        neg = ["01234567890",            # all distinct -> uniqueness fails
               "11111111111",            # too many repeats
               "+49 30 12345678", "FR1420041010050500013M02606",
               "0123456789",             # 10 digits
               "98765432100"]            # leading ok but check likely wrong / uniqueness
        neg += [x[:-1] + str((int(x[-1]) + 1) % 10) for x in valids[:12]]  # wrong check digit
        fp = sum(de_steuer_id.is_valid_steuer_id(x) for x in neg) / len(neg)
        self.assertLessEqual(fp, 0.01, f"fp={fp:.3f}")

    def test_uniqueness_required(self):
        # A correct-checksum number with all-distinct first 10 must still fail.
        self.assertFalse(de_steuer_id.is_valid_steuer_id("01234567890"))

    def test_first_digit_not_zero(self):
        v = _de_valids(1)[0]
        self.assertFalse(de_steuer_id.is_valid_steuer_id("0" + v[1:]))


class TestFrenchNir(unittest.TestCase):
    def test_recall(self):
        v = _fr_valids(25)
        self.assertEqual(len(v), 25)
        self.assertGreaterEqual(sum(fr_nir.is_valid_nir(x) for x in v) / len(v), 0.95)

    def test_canonical_example(self):
        # Documented valid NIR (spaced form).
        self.assertTrue(fr_nir.is_valid_nir("2 69 05 49 588 157 80"))

    def test_corsica_2a_2b(self):
        for dept in ("2A", "2B"):
            # sex(1) year(2) month(2) dept(2) commune(3) order(3) = 13
            body = "1" + "75" + "05" + dept + "123" + "456"
            self.assertEqual(len(body), 13)
            key = fr_nir.nir_key(body)
            self.assertIsNotNone(key)
            self.assertTrue(fr_nir.is_valid_nir(f"{body}{key:02d}"))

    def test_false_positive(self):
        valids = _fr_valids(25)
        neg = ["+33 6 12 34 56 78", "2026-06-09", "123456789012345",
               "DE89370400440532013000", "3850578006084"]
        neg += [x[:-1] + str((int(x[-1]) + 1) % 10) for x in valids[:12]]  # wrong key
        fp = sum(fr_nir.is_valid_nir(x) for x in neg) / len(neg)
        self.assertLessEqual(fp, 0.01, f"fp={fp:.3f}")


class TestPresidioRecognizers(unittest.TestCase):
    def test_all_register(self):
        for mod, ent in ((no_fnr, "NO_FNR"), (de_steuer_id, "DE_STEUER_ID"), (fr_nir, "FR_NIR")):
            try:
                recs = mod.get_recognizers()
            except ImportError:
                self.skipTest("presidio-analyzer not installed in this env")
            self.assertEqual(len(recs), 1)
            self.assertIn(ent, recs[0].get_supported_entities())


if __name__ == "__main__":
    unittest.main()
