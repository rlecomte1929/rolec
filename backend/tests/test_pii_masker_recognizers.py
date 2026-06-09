"""[AIQ-675 / AI-I.3f] pii_masker × custom recognizer registry — compatibility.

Validation criteria:
  - existing pii_masker behaviour is unchanged (covered by test_pii_masker.py;
    a couple of guards repeated here);
  - the checksum-validated recognizer wiring catches structured PII the
    shape-only regexes missed (notably FR/IT passport formats, previously
    leaking);
  - combined fixtures across the structured entity types hit recall >= 0.95.

The masker is presidio-free (lightweight wiring), so NER-based name masking is
out of scope here — it is a separately-ticketed spaCy upgrade.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from backend.app.services.pii_masker import mask_pii, is_already_masked
from backend.app.services.pii.presidio_recognizers import (
    no_fnr, de_steuer_id, fr_nir,
)

_MASK_TOKENS = ("[REDACTED_EMAIL]", "[REDACTED_PHONE]", "[REDACTED_IBAN]",
                "[REDACTED_PASSPORT]", "[REDACTED_SSN]", "[REDACTED_FNR]",
                "[REDACTED_ID]")


def _redacted(snippet: str, token: str) -> bool:
    """True if the sensitive token no longer appears verbatim after masking."""
    out = mask_pii(snippet)
    return token not in out and any(t in out for t in _MASK_TOKENS)


class TestExistingUnchanged(unittest.TestCase):
    def test_email_and_plain(self):
        self.assertEqual(mask_pii("write to a@b.com now"), "write to [REDACTED_EMAIL] now")
        self.assertEqual(mask_pii("just plain text"), "just plain text")

    def test_us_passport_letter_prefix_still_masks(self):
        self.assertIn("[REDACTED_PASSPORT]", mask_pii("passport M12345678 issued"))


class TestRecognizerWiring(unittest.TestCase):
    def test_fr_passport_format_now_masked(self):
        # 2 digits + 2 letters + 5 digits — invisible to the old `[A-Z]{1,2}\d{5,9}`.
        out = mask_pii("Passeport 19AB54321 délivré")
        self.assertIn("[REDACTED_PASSPORT]", out)
        self.assertNotIn("19AB54321", out)

    def test_it_passport_format_now_masked(self):
        out = mask_pii("Passaporto AA1234567 ok")
        self.assertIn("[REDACTED_PASSPORT]", out)
        self.assertNotIn("AA1234567", out)

    def test_valid_steuer_id_is_masked(self):
        # Build a valid Steuer-ID whose digits 3-4 are not a valid month, so the
        # NO-fnr regex can't claim it and the recognizer pass labels it.
        sid = None
        for seed in range(300):
            base = (seed % 9) + 1
            others = [d for d in range(10) if d != base][:8]
            rot = seed % 8
            others = others[rot:] + others[:rot]
            s = f"{base}{base}" + "".join(map(str, others))
            cand = s + str(de_steuer_id.steuer_id_check_digit(s))
            if de_steuer_id.is_valid_steuer_id(cand) and cand[2:4] not in {f"{m:02d}" for m in range(1, 13)} and cand[2:4][0] in "01":
                sid = cand
                break
        self.assertIsNotNone(sid)
        out = mask_pii(f"Steuer-ID {sid} on file")
        self.assertNotIn(sid, out)
        self.assertIn("[REDACTED_ID]", out)

    def test_import_safe_and_never_raises(self):
        # mask_pii must never raise even on odd input.
        for s in ["", "🙂🙂🙂", "a" * 5000, "FR76 3000 1007 1234 5678 9012 345"]:
            mask_pii(s)


class TestCombinedRecall(unittest.TestCase):
    def _combined_fixture(self):
        items = []
        # IBANs (valid)
        for iban in ["FR7630006000011234567890189", "DE89370400440532013000",
                     "NO9386011117947", "GB29NWBK60161331926819",
                     "ES9121000418450200051332", "NL91ABNA0417164300"]:
            items.append((f"IBAN {iban} please", iban))
        # FR passport (2 digits + 2 letters + 5 digits) / IT (2 letters + 7 digits)
        for p in ["19AB54321", "23ZZ00099", "45CD67890", "88XY12345"]:
            items.append((f"passeport {p}", p))
        for p in ["AA1234567", "YA9876543", "AB0001112"]:
            items.append((f"passaporto {p}", p))
        # NO fnr (valid by construction)
        n = 0
        seed = 0
        while n < 6:
            seed += 1
            dd = (seed % 28) + 1
            mm = (seed % 12) + 1
            yy = (seed * 7) % 100
            ind = (seed * 137) % 1000
            f9 = f"{dd:02d}{mm:02d}{yy:02d}{ind:03d}"
            ctrl = no_fnr.fnr_control_digits(f9)
            if ctrl is None:
                continue
            fnr = f"{f9}{ctrl[0]}{ctrl[1]}"
            items.append((f"fnr {fnr}", fnr))
            n += 1
        # FR NIR (valid by construction)
        for seed in range(1, 7):
            body = f"{1 if seed % 2 else 2}{seed % 100:02d}{(seed % 12) + 1:02d}{(seed % 95) + 1:02d}{(seed * 13) % 1000:03d}{(seed * 29) % 1000:03d}"
            nir = f"{body}{fr_nir.nir_key(body):02d}"
            items.append((f"NIR {nir}", nir))
        return items

    def test_overall_recall_at_least_95pct(self):
        fixture = self._combined_fixture()
        self.assertGreaterEqual(len(fixture), 25)
        masked = sum(1 for snip, tok in fixture if _redacted(snip, tok))
        recall = masked / len(fixture)
        leaks = [tok for snip, tok in fixture if not _redacted(snip, tok)]
        self.assertGreaterEqual(recall, 0.95, f"recall={recall:.3f}; leaks={leaks[:5]}")

    def test_idempotent(self):
        for snip, _ in self._combined_fixture()[:10]:
            once = mask_pii(snip)
            self.assertEqual(mask_pii(once), once)
            self.assertTrue(is_already_masked(once))


if __name__ == "__main__":
    unittest.main()
