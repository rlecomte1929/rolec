"""
Tests for backend/services/fx_service.py — T1.4.

Locks in the rate table so it stays in sync with the frontend mirror at
frontend/src/features/services/servicesCurrency.ts. If you change a rate on
one side without changing it on the other, this test fails before the drift
ships.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.fx_service import (  # noqa: E402
    DEFAULT_DISPLAY_CURRENCY,
    SUPPORTED_DISPLAY_CURRENCIES,
    USD_TO,
    convert_usd_to_display,
    normalize_display_currency,
)


class FxServiceTests(unittest.TestCase):
    def test_default_currency_is_usd(self) -> None:
        self.assertEqual(DEFAULT_DISPLAY_CURRENCY, "USD")
        self.assertEqual(USD_TO["USD"], 1.0)

    def test_supported_currencies_match_frontend(self) -> None:
        # Locked: must match SERVICES_DISPLAY_CURRENCIES in
        # frontend/src/features/services/servicesCurrency.ts.
        expected = {"USD", "EUR", "GBP", "CHF", "CAD", "AUD", "NOK", "SEK", "DKK", "JPY"}
        self.assertEqual(set(SUPPORTED_DISPLAY_CURRENCIES), expected)

    def test_rates_match_frontend_table(self) -> None:
        # Locked: each rate must match USD_TO in the frontend file at the
        # exact numeric value. Drift here is silent and breaks parity.
        expected = {
            "USD": 1.0,
            "EUR": 0.92,
            "GBP": 0.79,
            "CHF": 0.9,
            "CAD": 1.38,
            "AUD": 1.54,
            "NOK": 10.85,
            "SEK": 10.65,
            "DKK": 6.9,
            "JPY": 150.0,
        }
        self.assertEqual(USD_TO, expected)

    def test_normalize_falls_back_for_unknown_or_empty(self) -> None:
        self.assertEqual(normalize_display_currency(None), "USD")
        self.assertEqual(normalize_display_currency(""), "USD")
        self.assertEqual(normalize_display_currency("xyz"), "USD")
        self.assertEqual(normalize_display_currency("eur"), "EUR")  # case-insensitive
        self.assertEqual(normalize_display_currency(" GBP "), "GBP")

    def test_convert_usd_returns_none_for_none(self) -> None:
        self.assertIsNone(convert_usd_to_display(None, "EUR"))

    def test_convert_usd_to_eur(self) -> None:
        self.assertAlmostEqual(convert_usd_to_display(1000, "EUR"), 920.0, places=4)

    def test_convert_unknown_currency_falls_back_to_usd(self) -> None:
        # Mirrors the frontend's silent fallback.
        self.assertAlmostEqual(convert_usd_to_display(1000, "XYZ"), 1000.0, places=4)

    def test_convert_zero(self) -> None:
        self.assertEqual(convert_usd_to_display(0, "JPY"), 0.0)

    def test_jpy_rate_is_int_safe(self) -> None:
        # JPY has the largest multiplier; check the result is well-formed.
        result = convert_usd_to_display(1000, "JPY")
        self.assertEqual(result, 150_000.0)


if __name__ == "__main__":
    unittest.main()
