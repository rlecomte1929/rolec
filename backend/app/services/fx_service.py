"""
Display-only FX conversion for service estimates and policy caps.

This is the backend mirror of `frontend/src/features/services/servicesCurrency.ts`.
Rates are indicative planning values, not live FX — they exist so the API
returns the same numbers HR and the employee see in the Estimate Review
screen, regardless of who's calling.

T1.4 from the Sprint 2 execution plan: "Policy caps stored in USD nominal —
need display_currency param on the estimate endpoint so HR and employee see
the same number."

When the frontend later opts into the converted fields, both tiers display
identical values — same source of truth. Pulling live rates is a Phase 2
follow-up; the current rates match the frontend's table exactly so client +
server agree today.
"""
from __future__ import annotations

from typing import Dict, Optional

# Keep this in sync with frontend/src/features/services/servicesCurrency.ts
USD_TO: Dict[str, float] = {
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

DEFAULT_DISPLAY_CURRENCY = "USD"
SUPPORTED_DISPLAY_CURRENCIES = tuple(USD_TO.keys())


def normalize_display_currency(code: Optional[str]) -> str:
    """Normalize an incoming currency code; fall back to USD when unknown."""
    if not code:
        return DEFAULT_DISPLAY_CURRENCY
    cur = str(code).strip().upper()
    return cur if cur in USD_TO else DEFAULT_DISPLAY_CURRENCY


def convert_usd_to_display(usd: Optional[float], display_currency: str) -> Optional[float]:
    """
    Convert a USD-denominated amount to the display currency.

    Returns None when input is None (so callers can pass through optional
    fields without juggling sentinels). Currencies without a known rate
    fall back to USD (no-op) to mirror the frontend's silent fallback.
    """
    if usd is None:
        return None
    cur = normalize_display_currency(display_currency)
    rate = USD_TO.get(cur, 1.0)
    return float(usd) * rate
