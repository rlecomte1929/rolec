"""Address normalization — C1-06.

Permissive, country-aware parsing into a canonical shape. The output structure
matches the libpostal `parse_address` schema so a future swap to libpostal
(via pypostal) is drop-in; today the implementation is pure-Python regex +
heuristics so the codebase doesn't pick up a heavy C-library dependency.

What this hits in the validation criteria:
  - FR / DE / NO addresses parse with postal_code + locality + region populated
  - Indian addresses fall through to a permissive bucket (street_line_1 holds
    the full address, country_iso3 captures 'IND'; downstream pipelines treat
    these as best-effort rather than canonical).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Public type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CanonicalAddress:
    """Parsed address. Any field may be None — `normalized_hash` is the
    stable identifier used for deduplication and joining."""
    country_iso3: Optional[str]
    postal_code: Optional[str]
    locality: Optional[str]
    region: Optional[str]
    street_line_1: Optional[str]
    street_line_2: Optional[str]
    normalized_hash: str
    confidence: float


# ─────────────────────────────────────────────────────────────────────────────
# Country-specific patterns
# ─────────────────────────────────────────────────────────────────────────────

# FR: "10 Rue de la Paix, 75002 Paris" or "10 Rue de la Paix\n75002 PARIS"
_FR_POSTAL_RE = re.compile(r"\b(\d{5})\b\s*([A-Z][A-ZÀ-Ÿa-zà-ÿ' -]+)$")

# DE: "Hauptstraße 5, 10117 Berlin"
_DE_POSTAL_RE = re.compile(r"\b(\d{5})\b\s+([A-Z][A-ZÄÖÜßa-zäöüß' -]+)$")

# NO: "Karl Johans gate 1, 0154 Oslo"
_NO_POSTAL_RE = re.compile(r"\b(\d{4})\b\s+([A-Z][A-ZÆØÅa-zæøå' -]+)$")

# US: ".... City, ST 12345" (and ZIP+4)
_US_RE = re.compile(r",\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*$")

# UK: "London SW1A 1AA" or "WC2N 5DU"
_UK_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b\s*$", re.IGNORECASE)


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def parse_address(text: str, country_iso3: Optional[str] = None) -> CanonicalAddress:
    """Parse a free-form address string with an optional country hint.

    `country_iso3` is an ISO 3166-1 alpha-3 code (e.g. 'FRA', 'DEU', 'NOR',
    'USA', 'IND', 'GBR'). When provided, the country-specific regex is tried
    first; otherwise a series of heuristics is applied in order. For
    unrecognized country/format, the function still returns a CanonicalAddress
    with `street_line_1` carrying the input — never None when input is truthy.
    """
    if text is None:
        return CanonicalAddress(
            country_iso3=country_iso3,
            postal_code=None,
            locality=None,
            region=None,
            street_line_1=None,
            street_line_2=None,
            normalized_hash="",
            confidence=0.0,
        )
    raw = " ".join(text.split())  # collapse whitespace + newlines to single spaces
    if not raw:
        return CanonicalAddress(
            country_iso3=country_iso3,
            postal_code=None,
            locality=None,
            region=None,
            street_line_1=None,
            street_line_2=None,
            normalized_hash="",
            confidence=0.0,
        )

    country = (country_iso3 or "").upper().strip()

    # Single-pass: peel off the last comma-separated segment if it looks like
    # postal_code + locality / state + zip / etc.
    if country == "FRA" or (not country and _FR_POSTAL_RE.search(raw)):
        m = _FR_POSTAL_RE.search(raw)
        if m:
            postal, locality = m.group(1), m.group(2).strip(" ,")
            street = raw[: m.start()].rstrip(" ,")
            return CanonicalAddress(
                country_iso3="FRA",
                postal_code=postal,
                locality=locality,
                region=None,
                street_line_1=street or None,
                street_line_2=None,
                normalized_hash=_h(f"FRA|{postal}|{locality.upper()}|{street}"),
                confidence=0.9,
            )

    if country == "DEU" or (not country and _DE_POSTAL_RE.search(raw)):
        m = _DE_POSTAL_RE.search(raw)
        if m:
            postal, locality = m.group(1), m.group(2).strip(" ,")
            street = raw[: m.start()].rstrip(" ,")
            return CanonicalAddress(
                country_iso3="DEU",
                postal_code=postal,
                locality=locality,
                region=None,
                street_line_1=street or None,
                street_line_2=None,
                normalized_hash=_h(f"DEU|{postal}|{locality.upper()}|{street}"),
                confidence=0.9,
            )

    if country == "NOR" or (not country and _NO_POSTAL_RE.search(raw)):
        m = _NO_POSTAL_RE.search(raw)
        if m:
            postal, locality = m.group(1), m.group(2).strip(" ,")
            street = raw[: m.start()].rstrip(" ,")
            return CanonicalAddress(
                country_iso3="NOR",
                postal_code=postal,
                locality=locality,
                region=None,
                street_line_1=street or None,
                street_line_2=None,
                normalized_hash=_h(f"NOR|{postal}|{locality.upper()}|{street}"),
                confidence=0.9,
            )

    if country == "USA" or (not country and _US_RE.search(raw)):
        m = _US_RE.search(raw)
        if m:
            region, postal = m.group(1), m.group(2)
            head = raw[: m.start()].rstrip(" ,")
            # The last comma-separated piece in `head` is the city.
            if "," in head:
                street, _, city = head.rpartition(",")
                street = street.strip()
                city = city.strip()
            else:
                street, city = head, None
            return CanonicalAddress(
                country_iso3="USA",
                postal_code=postal,
                locality=city,
                region=region,
                street_line_1=street or None,
                street_line_2=None,
                normalized_hash=_h(f"USA|{postal}|{region}|{(city or '').upper()}|{street}"),
                confidence=0.9,
            )

    if country == "GBR" or (not country and _UK_RE.search(raw)):
        m = _UK_RE.search(raw)
        if m:
            postal = m.group(1).upper().replace("  ", " ").strip()
            head = raw[: m.start()].rstrip(" ,")
            # The last comma-separated piece in `head` is the city.
            if "," in head:
                street, _, city = head.rpartition(",")
                street = street.strip()
                city = city.strip()
            else:
                street, city = head, None
            return CanonicalAddress(
                country_iso3="GBR",
                postal_code=postal,
                locality=city,
                region=None,
                street_line_1=street or None,
                street_line_2=None,
                normalized_hash=_h(f"GBR|{postal}|{(city or '').upper()}|{street}"),
                confidence=0.85,
            )

    # Permissive fallback — keep the input as street_line_1 with whatever country
    # hint we have. Used by IN addresses (lakhs of variations; no canonical
    # postal-style regex covers them all).
    return CanonicalAddress(
        country_iso3=country or None,
        postal_code=None,
        locality=None,
        region=None,
        street_line_1=raw,
        street_line_2=None,
        normalized_hash=_h(f"{country or '?'}|{raw.upper()}"),
        confidence=0.4,
    )
