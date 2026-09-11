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
identical values — same source of truth. Live rates are snapshotted into
``fx_rates`` by a cron in the authoring layer ([AIQ-2271]); this module
reads that table when a connection is passed and otherwise uses the
hardcoded table so ``convert_usd_to_display`` stays pure.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text

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

# ISO-3166 alpha-2 destination country → default display currency (AIQ-1327).
# Mirror of COUNTRY_TO_CURRENCY in frontend/src/features/services/servicesCurrency.ts:
# eurozone members all map to EUR; any country whose currency we don't display
# falls through normalize_display_currency() to USD (the FX baseline).
COUNTRY_TO_CURRENCY: Dict[str, str] = {
    # Eurozone
    "AT": "EUR", "BE": "EUR", "HR": "EUR", "CY": "EUR", "EE": "EUR", "FI": "EUR",
    "FR": "EUR", "DE": "EUR", "GR": "EUR", "IE": "EUR", "IT": "EUR", "LV": "EUR",
    "LT": "EUR", "LU": "EUR", "MT": "EUR", "NL": "EUR", "PT": "EUR", "SK": "EUR",
    "SI": "EUR", "ES": "EUR",
    # Other displayed currencies
    "GB": "GBP", "US": "USD", "CH": "CHF", "CA": "CAD", "AU": "AUD", "NO": "NOK",
    "SE": "SEK", "DK": "DKK", "JP": "JPY",
    # utils/countries uses 'UK' for the United Kingdom while ISO is 'GB' — alias (AIQ-1620).
    "UK": "GBP",
}


def normalize_display_currency(code: Optional[str]) -> str:
    """Normalize an incoming currency code; fall back to USD when unknown."""
    if not code:
        return DEFAULT_DISPLAY_CURRENCY
    cur = str(code).strip().upper()
    return cur if cur in USD_TO else DEFAULT_DISPLAY_CURRENCY


def default_currency_for_country(country: Optional[str]) -> str:
    """Default display currency for an ISO alpha-2 destination country.

    Mirrors the frontend's getDefaultCurrencyForCountry: map the country to its
    currency, then normalize (so an unknown/unsupported country degrades to USD).
    """
    code = COUNTRY_TO_CURRENCY.get(str(country or "").strip().upper())
    return normalize_display_currency(code)


def usd_to_table(conn: Any = None) -> Dict[str, float]:
    """USD→quote table: latest ``fx_rates`` snapshot, else the hardcoded fallback."""
    rates = dict(USD_TO)
    if conn is None:
        return rates
    try:
        row = conn.execute(
            text(
                "SELECT as_of_date FROM fx_rates WHERE UPPER(base_currency) = 'USD' "
                "ORDER BY as_of_date DESC LIMIT 1"
            )
        ).first()
        if not row:
            return rates
        as_of = row[0]
        result = conn.execute(
            text(
                "SELECT quote_currency, rate FROM fx_rates "
                "WHERE UPPER(base_currency) = 'USD' AND as_of_date = :d"
            ),
            {"d": as_of},
        )
        for quote, rate in result:
            q = str(quote or "").strip().upper()
            if q:
                rates[q] = float(rate)
        rates["USD"] = 1.0
        return rates
    except Exception:
        return dict(USD_TO)


def rate_between(from_currency: str, to_currency: str, conn: Any = None) -> Optional[float]:
    """Units of ``to`` per 1 unit of ``from``. Same-currency is 1.0. None if unknown."""
    a = str(from_currency or "").strip().upper()
    b = str(to_currency or "").strip().upper()
    if not a or not b:
        return None
    if a == b:
        return 1.0
    table = usd_to_table(conn)
    if a not in table or b not in table:
        return None
    src = table[a]
    if not src:
        return None
    return table[b] / src


def snapshot_as_of(conn: Any = None) -> Optional[date]:
    """Date of the latest USD snapshot, or None when falling back to hardcoded."""
    if conn is None:
        return None
    try:
        row = conn.execute(
            text(
                "SELECT as_of_date FROM fx_rates WHERE UPPER(base_currency) = 'USD' "
                "ORDER BY as_of_date DESC LIMIT 1"
            )
        ).first()
        if not row or row[0] is None:
            return None
        val = row[0]
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return None


def convert_usd_to_display(usd: Optional[float], display_currency: str) -> Optional[float]:
    """
    Convert a USD-denominated amount to the display currency.

    Returns None when input is None (so callers can pass through optional
    fields without juggling sentinels). Currencies without a known rate
    fall back to USD (no-op) to mirror the frontend's silent fallback.

    Pure: uses the hardcoded table only so tests stay deterministic.
    """
    if usd is None:
        return None
    cur = normalize_display_currency(display_currency)
    rate = USD_TO.get(cur, 1.0)
    return float(usd) * rate


def convert_with_snapshot(
    amount: float,
    from_currency: str,
    to_currency: str,
    conn: Any = None,
) -> Tuple[Optional[float], Optional[float], Optional[date]]:
    """Return (amount_in_to, rate_from_to, snapshot_date). Rate 1.0 when same currency."""
    rate = rate_between(from_currency, to_currency, conn)
    if rate is None:
        return None, None, snapshot_as_of(conn)
    as_of = snapshot_as_of(conn)
    if as_of is None:
        as_of = date.today()
    return float(amount) * rate, rate, as_of
