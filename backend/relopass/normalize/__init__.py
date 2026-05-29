"""Deterministic normalization primitives — C1-06.

Pure-Python (no LLM calls, no external services) primitives that turn
free-form text into canonical forms suitable for indexing, comparison,
and downstream entity resolution.

Modules:
    names      — surname / given-name normalization with ICAO 9303 §6
                 transliteration and particle handling
    dates      — 4-rule precedence to ISO 8601 with confidence + locale-hint findings
    addresses  — permissive country-aware parsing (libpostal-compatible shape
                 but no libpostal dependency required)
    employers  — legal-suffix stripping + registry-id format detection
                 (SIREN / HRB / Brønnøysund organisasjonsnummer / FEIN / etc.)
    money      — locale-aware amount + currency parsing into Decimal

Modules MUST NOT import from `backend/app/`, `fastapi`, `sqlalchemy`, or any
vendor SDK. They are the building blocks the higher layers compose against.
"""
from .names import normalize_name, NormalizedName
from .dates import parse_date, ParsedDate, LocaleHintSuggestion
from .addresses import parse_address, CanonicalAddress
from .employers import normalize_employer, NormalizedEmployer
from .money import parse_money, ParsedMoney

__all__ = [
    "normalize_name",
    "NormalizedName",
    "parse_date",
    "ParsedDate",
    "LocaleHintSuggestion",
    "parse_address",
    "CanonicalAddress",
    "normalize_employer",
    "NormalizedEmployer",
    "parse_money",
    "ParsedMoney",
]
