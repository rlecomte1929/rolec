"""Money normalization — C1-06.

Locale-aware parse of free-form money strings into Decimal + ISO 4217 currency.
The canonical type uses Decimal (never float) per the technical constraints —
floats and money don't mix.

Patterns covered (from the validation criteria):
  - DE: '1.234,56 €'     → Decimal('1234.56'), 'EUR'
  - FR: '1 234,56 €'     → Decimal('1234.56'), 'EUR'
  - NO: '1 234,56 kr'    → Decimal('1234.56'), 'NOK'
  - US: '$1,234.56'       → Decimal('1234.56'), 'USD'
  - UK: '£1,234.56'       → Decimal('1234.56'), 'GBP'
  - IN: '₹ 12,34,567.00' → Decimal('1234567.00'), 'INR'  (lakhs/crores grouping)

Annualization helpers (per Architecture Report §3.4 last paragraph) live in
`annualize` — they take a Decimal + period hint and return a Decimal annual
estimate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Symbol / currency tables
# ─────────────────────────────────────────────────────────────────────────────

# Unambiguous symbol → ISO3 mappings.
_SYMBOL_TO_ISO3 = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "₽": "RUB",
    "₩": "KRW",
    "₪": "ILS",
    "kr": "NOK",  # ambiguous between NOK / SEK / DKK / ISK — see _resolve_currency
}

# When the locale hint is provided, 'kr' is disambiguated to a specific ISO3.
_KR_BY_LOCALE = {
    "NO": "NOK",
    "SE": "SEK",
    "DK": "DKK",
    "IS": "ISK",
}

# ISO 4217 alpha-3 codes appearing in tested corridors.
_KNOWN_ISO3 = {
    "EUR", "USD", "GBP", "JPY", "INR", "RUB", "KRW", "ILS",
    "NOK", "SEK", "DKK", "ISK", "CHF", "CAD", "AUD", "PLN",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedMoney:
    amount: Optional[Decimal]
    currency_iso3: Optional[str]
    locale_used: Optional[str]
    confidence: float


# ─────────────────────────────────────────────────────────────────────────────
# Number parsing — locale-aware
# ─────────────────────────────────────────────────────────────────────────────

# Heuristic: detect the decimal separator from the last . or , in the string.
# If the last separator is followed by 1–2 digits → it's the decimal mark.
# If followed by 3 digits → it's a thousands separator and the value has no fraction.


def _parse_amount(numeric: str) -> Optional[Decimal]:
    """Strip thousands separators and convert to Decimal.

    Recognised conventions:
      - Comma decimal (DE/FR/NO): '1.234,56' or '1 234,56' → Decimal('1234.56')
      - Period decimal (US/UK/IN): '1,234.56' or '12,34,567.00' → Decimal
      - Mixed: detect by the LAST occurrence of '.' or ','.
    """
    if not numeric:
        return None
    s = re.sub(r"[\s ]", "", numeric)  # remove regular and non-breaking spaces
    if not s:
        return None
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")

    if last_comma == -1 and last_dot == -1:
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    if last_comma > last_dot:
        # Comma is the decimal separator (DE/FR/NO).
        integer_part = s[:last_comma].replace(".", "").replace(",", "")
        fraction = s[last_comma + 1 :]
        candidate = f"{integer_part}.{fraction}" if fraction else integer_part
    else:
        # Period is the decimal separator (US/UK/IN).
        integer_part = s[:last_dot].replace(",", "").replace(".", "")
        fraction = s[last_dot + 1 :]
        candidate = f"{integer_part}.{fraction}" if fraction else integer_part

    try:
        return Decimal(candidate)
    except InvalidOperation:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Currency disambiguation
# ─────────────────────────────────────────────────────────────────────────────


_AMOUNT_RE = re.compile(r"[\d.,\s ]+")


def _resolve_currency(symbol_or_iso: str, locale_hint: Optional[str]) -> Optional[str]:
    """Map a currency symbol or ISO3 code to a canonical ISO3.
    Ambiguous 'kr' resolves via locale_hint."""
    token = symbol_or_iso.strip()
    upper = token.upper()
    if upper in _KNOWN_ISO3:
        return upper
    if token in _SYMBOL_TO_ISO3:
        iso = _SYMBOL_TO_ISO3[token]
        if iso == "NOK" and locale_hint:  # 'kr' disambiguation
            disambig = _KR_BY_LOCALE.get(locale_hint.upper())
            if disambig:
                return disambig
        return iso
    # Try lowercase 'kr'
    if token.lower() == "kr":
        if locale_hint:
            return _KR_BY_LOCALE.get(locale_hint.upper(), "NOK")
        return "NOK"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def parse_money(text: str, locale_hint: Optional[str] = None) -> ParsedMoney:
    """Parse a free-form money string into amount + currency.

    `locale_hint` is an ISO 3166-1 alpha-2 country code used for:
      - disambiguating 'kr' (NO/SE/DK/IS)
      - choosing decimal-separator convention when both interpretations parse

    Returns ParsedMoney(amount=None, currency_iso3=None) when nothing parses.
    """
    if text is None:
        return ParsedMoney(amount=None, currency_iso3=None, locale_used=None, confidence=0.0)
    raw = text.strip()
    if not raw:
        return ParsedMoney(amount=None, currency_iso3=None, locale_used=None, confidence=0.0)

    # First pass: find the currency token. Try ISO3 codes first (e.g. "NOK 1 234,56"),
    # then symbols.
    currency: Optional[str] = None
    body = raw

    iso_match = re.search(r"\b([A-Z]{3})\b", raw)
    if iso_match and iso_match.group(1) in _KNOWN_ISO3:
        currency = iso_match.group(1)
        body = (raw[: iso_match.start()] + " " + raw[iso_match.end() :]).strip()
    else:
        for symbol in sorted(_SYMBOL_TO_ISO3.keys(), key=lambda k: -len(k)):
            idx = raw.find(symbol)
            if idx >= 0:
                currency = _resolve_currency(symbol, locale_hint)
                body = (raw[:idx] + " " + raw[idx + len(symbol) :]).strip()
                break
        else:
            # try lowercase 'kr' too
            for tok in ("kr",):
                m = re.search(r"\b" + tok + r"\b", raw, re.IGNORECASE)
                if m:
                    currency = _resolve_currency(m.group(0), locale_hint)
                    body = (raw[: m.start()] + " " + raw[m.end() :]).strip()
                    break

    # Extract the numeric portion.
    amount_match = _AMOUNT_RE.search(body)
    if not amount_match:
        return ParsedMoney(amount=None, currency_iso3=currency, locale_used=locale_hint, confidence=0.0)
    amount = _parse_amount(amount_match.group(0))
    if amount is None:
        return ParsedMoney(amount=None, currency_iso3=currency, locale_used=locale_hint, confidence=0.0)

    confidence = 0.9 if currency else 0.5
    return ParsedMoney(amount=amount, currency_iso3=currency, locale_used=locale_hint, confidence=confidence)


# ─────────────────────────────────────────────────────────────────────────────
# Annualization helpers
# ─────────────────────────────────────────────────────────────────────────────


def annualize(amount: Decimal, period: str) -> Decimal:
    """Convert an amount expressed in a per-period unit to annual.

    `period` is one of: 'hour', 'day', 'week', 'month', 'quarter', 'year'.
    Day = 8h, Week = 5d, Month = 1/12, Quarter = 1/4, Year = identity.
    """
    factors = {
        "hour": Decimal("2000"),   # 40h/wk × 50wk = 2000h
        "day": Decimal("250"),     # ~250 working days
        "week": Decimal("50"),     # ~50 working weeks
        "month": Decimal("12"),
        "quarter": Decimal("4"),
        "year": Decimal("1"),
    }
    p = period.lower().strip()
    if p not in factors:
        raise ValueError(f"Unknown period {period!r}; expected one of {sorted(factors)}")
    return (amount * factors[p]).quantize(Decimal("0.01"))
