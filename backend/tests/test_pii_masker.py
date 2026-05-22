"""
Tests for [P5-9 H1/C2] PII masker.

Covers all 5 PII patterns from the audit (phone, IBAN, passport, SSN,
national ID), plus the contracts the masker advertises:
  - idempotency (mask once or twice → same string)
  - generic ID fallback
  - email
  - empty/None safety
  - `safe_log_text` truncates THEN masks
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.pii_masker import (  # noqa: E402
    mask_pii,
    safe_log_text,
    is_already_masked,
)


class PiiMaskerTests(unittest.TestCase):

    # ── empty / null safety ──────────────────────────────────────────────────

    def test_empty_string_returns_empty(self):
        self.assertEqual(mask_pii(""), "")

    def test_none_passes_through(self):
        self.assertIsNone(mask_pii(None))  # type: ignore[arg-type]

    def test_plain_text_unchanged(self):
        self.assertEqual(
            mask_pii("What is the housing allowance for managers?"),
            "What is the housing allowance for managers?",
        )

    # ── pattern 1: phone ─────────────────────────────────────────────────────

    def test_masks_international_phone(self):
        self.assertEqual(
            mask_pii("Call me at +33 6 12 34 56 78 please"),
            "Call me at [REDACTED_PHONE] please",
        )

    def test_masks_us_phone(self):
        self.assertEqual(
            mask_pii("My number is 415-555-1234"),
            "My number is [REDACTED_PHONE]",
        )

    # ── pattern 2: IBAN ──────────────────────────────────────────────────────

    def test_masks_french_iban(self):
        text = "Send to FR76 3000 1007 1234 5678 9012 345"
        out = mask_pii(text)
        self.assertIn("[REDACTED_IBAN]", out)
        self.assertNotIn("FR76", out)

    def test_masks_norwegian_iban(self):
        text = "Pay NO9386011117947 by Friday"
        out = mask_pii(text)
        self.assertIn("[REDACTED_IBAN]", out)

    # ── pattern 3: passport ──────────────────────────────────────────────────

    def test_masks_eu_passport_format(self):
        text = "My passport AB123456 expires next year"
        out = mask_pii(text)
        self.assertIn("[REDACTED_PASSPORT]", out)
        self.assertNotIn("AB123456", out)

    def test_masks_us_passport_letter_prefix(self):
        # US passports issued post-2007 are "M" + 8 digits.
        text = "Passport M12345678 was renewed"
        out = mask_pii(text)
        self.assertIn("[REDACTED_PASSPORT]", out)
        self.assertNotIn("M12345678", out)

    def test_masks_bare_9_digits_as_ssn(self):
        # 9 digits with no separator is ambiguous (SSN or US passport).
        # The masker labels it SSN — the important contract is that the
        # raw number doesn't survive.
        text = "Number 123456789 logged"
        out = mask_pii(text)
        self.assertIn("[REDACTED_", out)
        self.assertNotIn("123456789", out)

    # ── pattern 4: SSN variants ──────────────────────────────────────────────

    def test_masks_us_ssn_dashed(self):
        self.assertIn(
            "[REDACTED_SSN]", mask_pii("SSN 123-45-6789"),
        )

    def test_masks_us_ssn_no_separator(self):
        self.assertIn(
            "[REDACTED_SSN]", mask_pii("SSN 123456789"),
        )

    def test_masks_french_insee(self):
        # 1 84 12 75 116 001 23 — valid INSEE shape
        self.assertIn(
            "[REDACTED_SSN]",
            mask_pii("Mon numéro INSEE est 1 84 12 75 116 001 23"),
        )

    def test_masks_norwegian_fnr(self):
        # 01017012345 — DDMMYY + 5 digits
        self.assertIn(
            "[REDACTED_FNR]",
            mask_pii("Mitt fødselsnummer er 01017012345"),
        )

    # ── pattern 5: email + generic ID ────────────────────────────────────────

    def test_masks_email(self):
        self.assertEqual(
            mask_pii("Contact alice.smith+work@example.co.uk for details"),
            "Contact [REDACTED_EMAIL] for details",
        )

    def test_generic_id_fallback(self):
        # Pattern that's not email/phone/IBAN/SSN/passport but looks like
        # an ID: letters + digits or long digit run with letters
        out = mask_pii("Booking reference XYZ12345 confirmed")
        self.assertIn("[REDACTED_", out)
        self.assertNotIn("XYZ12345", out)

    # ── idempotency ──────────────────────────────────────────────────────────

    def test_idempotent_double_mask(self):
        text = "Call +33 6 12 34 56 78 about passport AB123456"
        once = mask_pii(text)
        twice = mask_pii(once)
        self.assertEqual(once, twice)

    def test_already_masked_detection(self):
        self.assertTrue(is_already_masked("Foo [REDACTED_PHONE] bar"))
        self.assertFalse(is_already_masked("Foo bar"))

    # ── multi-pattern in one string ──────────────────────────────────────────

    def test_masks_multiple_patterns_in_one_string(self):
        text = (
            "Hi, I'm at +33 6 12 34 56 78, email alice@example.com, "
            "passport AB123456, IBAN FR7630001007123456789012345"
        )
        out = mask_pii(text)
        self.assertIn("[REDACTED_PHONE]", out)
        self.assertIn("[REDACTED_EMAIL]", out)
        self.assertIn("[REDACTED_PASSPORT]", out)
        self.assertIn("[REDACTED_IBAN]", out)

    # ── safe_log_text ────────────────────────────────────────────────────────

    def test_safe_log_text_short_string_unchanged(self):
        self.assertEqual(
            safe_log_text("Short message", max_len=120),
            "Short message",
        )

    def test_safe_log_text_truncates_and_appends_ellipsis(self):
        long_text = "A" * 200
        out = safe_log_text(long_text, max_len=50)
        # Expect truncated to 50 + ellipsis
        self.assertTrue(out.endswith("…"))
        self.assertEqual(len(out), 51)  # 50 chars + 1 ellipsis char

    def test_safe_log_text_masks_pii_after_truncate(self):
        text = "Booking reference AB123456 with phone +33612345678"
        out = safe_log_text(text, max_len=200)
        self.assertIn("[REDACTED_", out)
        self.assertNotIn("AB123456", out)


if __name__ == "__main__":
    unittest.main()
