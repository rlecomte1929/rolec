"""Employer normalization — C1-06.

Two operations:

  1. Legal-suffix stripping. A company is "the same company" whether the
     incoming text says "ACME SAS", "Acme S.A.S.", "Acme s.a.s." etc.
     We strip the trailing legal form and keep both forms — display
     (with suffix) and stripped (for indexing / blocking).

  2. Registry-ID format detection. France's SIREN (9 digits), Germany's
     HRB (variable + city prefix), Norway's Brønnøysund organisasjonsnummer
     (9 digits), the US FEIN (NN-NNNNNNN). Per PF-1 the registry_id column
     stores free-form TEXT — this function doesn't reject anything, it just
     tags the detected format so downstream consumers can render it
     appropriately.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Suffix catalog
# ─────────────────────────────────────────────────────────────────────────────

# Per-country legal-form suffixes. Stored as a set of normalized tokens
# (uppercase, no dots, no leading/trailing whitespace). Multi-word entries
# (e.g. 'private limited') are matched as phrases.
_LEGAL_SUFFIXES = {
    # France
    "SARL", "SAS", "SA", "SCI", "SCS", "SNC", "SCOP", "EURL", "SASU", "SCA",
    # Germany / Austria / Switzerland
    "GMBH", "AG", "KG", "OHG", "UG", "EG", "MBH", "GMBH & CO KG", "GMBH CO KG",
    # Norway
    "AS", "ANS", "ENK", "BA", "ASA",
    # Sweden / Finland / Denmark / Iceland
    "AB", "HB", "KB", "OY", "OYJ", "KY", "APS", "EHF", "OHF",
    # Netherlands / Belgium
    "BV", "NV", "VOF",
    # UK / Ireland
    "LTD", "LIMITED", "PLC", "LLP", "LP",
    # US / Canada
    "LLC", "INC", "CORP", "CORPORATION", "CO", "COMPANY", "INCORPORATED",
    # India
    "PRIVATE LIMITED", "PVT LTD", "PVT LIMITED",
    # Spain / Italy / Portugal
    "SL", "SLU", "SAU", "SRL", "SPA", "SOC", "LDA",
}

# Sort suffixes by descending length for greedy matching (so "PRIVATE LIMITED"
# matches before "LIMITED" alone).
_LEGAL_SUFFIXES_ORDERED = sorted(_LEGAL_SUFFIXES, key=lambda s: -len(s))


# ─────────────────────────────────────────────────────────────────────────────
# Registry-ID formats
# ─────────────────────────────────────────────────────────────────────────────

# Patterns are deliberately liberal — the spec only requires that the format
# be DETECTED and tagged, not enforced. PF-1 mandates registry_id schema
# flexibility, so any non-empty input passes through with the best-effort tag.
_REGISTRY_PATTERNS = (
    # (tag, regex, country_iso3_hint)
    ("SIREN", re.compile(r"^\s*(\d{3}\s?\d{3}\s?\d{3})\s*$"), "FRA"),
    ("SIRET", re.compile(r"^\s*(\d{3}\s?\d{3}\s?\d{3}\s?\d{5})\s*$"), "FRA"),
    ("HRB",   re.compile(r"^\s*HRB\s*\d{1,8}(?:\s+\([A-Za-zÄÖÜäöüß ]+\))?\s*$", re.IGNORECASE), "DEU"),
    ("ORGNR", re.compile(r"^\s*\d{3}\s?\d{3}\s?\d{3}\s*$"), "NOR"),
    ("FEIN",  re.compile(r"^\s*\d{2}-\d{7}\s*$"), "USA"),
    ("CRN",   re.compile(r"^\s*\d{8}\s*$"), "GBR"),  # UK Companies House
    ("CIN",   re.compile(r"^\s*[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\s*$"), "IND"),  # Indian CIN
)


def _detect_registry(text: str, country_iso3: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return (kind, country_iso3) of a detected registry-id format, or (None, None)."""
    if not text:
        return None, None
    s = text.strip()
    target = (country_iso3 or "").upper().strip()
    for kind, pattern, country_hint in _REGISTRY_PATTERNS:
        if target and country_hint != target:
            # Skip patterns that don't match the explicit country hint, unless
            # no hint is provided.
            continue
        if pattern.match(s):
            return kind, country_hint
    # Last attempt — try without honouring the country hint.
    if target:
        for kind, pattern, country_hint in _REGISTRY_PATTERNS:
            if pattern.match(s):
                return kind, country_hint
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# Public type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NormalizedEmployer:
    legal_name_display: str          # original casing, suffix preserved
    legal_name_stripped: str         # uppercased, suffix removed, diacritic-folded
    legal_suffix: Optional[str]      # canonical (uppercase, no punctuation) — None if no match
    registry_id: Optional[str]
    registry_id_kind: Optional[str]  # SIREN | SIRET | HRB | ORGNR | FEIN | CRN | CIN | None
    country_iso3: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _strip_diacritics(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


_PUNCT_RE = re.compile(r"[.,]")
_WS_RE = re.compile(r"\s+")


def _canonical_tokens(text: str) -> str:
    """Uppercase + strip punctuation from suffix-style tokens for matching."""
    return _WS_RE.sub(" ", _PUNCT_RE.sub("", text)).strip().upper()


def _split_off_suffix(name: str) -> tuple[str, Optional[str]]:
    """Find a trailing legal suffix; return (stripped_name, canonical_suffix).
    The match is case-insensitive and tolerant of dots."""
    if not name:
        return name, None
    canonical = _canonical_tokens(name)
    for suffix in _LEGAL_SUFFIXES_ORDERED:
        if canonical.endswith(" " + suffix) or canonical == suffix:
            # Strip the original ending — preserve original casing of the body.
            tokens = name.rsplit(maxsplit=suffix.count(" ") + 1)
            stripped = " ".join(tokens[: -(suffix.count(" ") + 1)])
            return stripped.rstrip(" .,"), suffix
    return name, None


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def normalize_employer(
    text: str,
    country_iso3: Optional[str] = None,
    registry_id: Optional[str] = None,
) -> NormalizedEmployer:
    """Normalize an employer legal-name + optional registry-id.

    `country_iso3` is a soft hint used to disambiguate registry-id format
    when the input could match multiple national patterns (e.g. SIREN 9-digit
    blocks visually overlap with Brønnøysund organisasjonsnummer; the hint
    disambiguates which the caller intended).
    """
    if text is None:
        text = ""
    raw = text.strip()
    stripped, suffix = _split_off_suffix(raw)
    legal_name_stripped = _strip_diacritics(stripped).upper().strip()

    reg_kind: Optional[str] = None
    reg_country: Optional[str] = None
    if registry_id:
        reg_kind, reg_country = _detect_registry(registry_id, country_iso3)

    final_country = (country_iso3 or reg_country or None)

    return NormalizedEmployer(
        legal_name_display=raw,
        legal_name_stripped=legal_name_stripped,
        legal_suffix=suffix,
        registry_id=registry_id.strip() if registry_id else None,
        registry_id_kind=reg_kind,
        country_iso3=final_country,
    )
