"""Single source of truth for country/corridor key resolution across the two
requirements engines (AIQ-1473b).

Background: the two requirements paths keyed countries differently, which let a
case silently miss all its requirements (AIQ-1349):

  * Path A — immigration_requirement_service — keys immigration_requirements by
    ISO corridor codes ("FR", "DE").
  * Path B — requirements_builder — keys requirement_items by the catalog's FULL
    UPPERCASE country name ("GERMANY"), resolved from a case's ISO destination.

AIQ-1473a chose **ISO alpha-2 UPPERCASE** as the single canonical internal key.
This module owns that mapping so neither path carries its own private copy.

`to_iso` returns ``None`` for an unrecognised value on purpose: it lets callers
fail closed (surface "not covered") instead of querying with a bad key and
getting an empty result that reads as "nothing required" — the 1473c follow-up.
"""
from __future__ import annotations

from typing import Optional

# Canonical ISO alpha-2 (UPPERCASE) → requirement catalog country_code
# (FULL UPPERCASE name). The one place this mapping lives.
_ISO_TO_CATALOG_NAME = {
    "DE": "GERMANY",
    "NO": "NORWAY",
    "SG": "SINGAPORE",
    "GB": "UNITED KINGDOM",
    "US": "UNITED STATES",
    "FR": "FRANCE",
    "NL": "NETHERLANDS",
}

# Non-standard inputs seen in the data that map onto a canonical ISO code.
_ISO_ALIASES = {
    "UK": "GB",
    "USA": "US",
}

# Reverse lookup: catalog full name → ISO. Derived so there is no second map to
# keep in sync.
_CATALOG_NAME_TO_ISO = {name: iso for iso, name in _ISO_TO_CATALOG_NAME.items()}


def to_iso(raw: Optional[str]) -> Optional[str]:
    """Resolve a country value to the canonical ISO alpha-2 UPPERCASE key.

    Accepts an ISO code ("SG"), a known alias ("UK", "USA"), or a full country
    name in any case ("Singapore"). Returns ``None`` when the value is empty or
    unrecognised, so callers can fail closed rather than look up a bad key.
    """
    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None
    if s in _ISO_ALIASES:
        return _ISO_ALIASES[s]
    if s in _ISO_TO_CATALOG_NAME:
        return s
    if s in _CATALOG_NAME_TO_ISO:
        return _CATALOG_NAME_TO_ISO[s]
    return None


def iso_to_catalog_name(iso: Optional[str]) -> Optional[str]:
    """ISO alpha-2 → the requirement_items.country_code FULL-NAME convention.

    Returns ``None`` for an unknown/empty ISO code.
    """
    if not iso:
        return None
    return _ISO_TO_CATALOG_NAME.get(iso.strip().upper())


def resolve_catalog_country(dest: Optional[str]) -> str:
    """Resolve a case destination (ISO code or name) to the requirement catalog's
    country_code naming (FULL UPPERCASE name).

    Behaviour-preserving replacement for the former private
    ``requirements_builder._resolve_catalog_country``: a value we have catalog
    data for resolves to its full name; anything else falls back to the raw value
    upper-cased (no catalog rows exist for it yet anyway); empty → ``"UNKNOWN"``.
    """
    iso = to_iso(dest)
    if iso:
        name = iso_to_catalog_name(iso)
        if name:
            return name
    if not dest or not dest.strip():
        return "UNKNOWN"
    return dest.strip().upper()


def normalize_corridor_code(raw: Optional[str]) -> str:
    """Normalise a corridor code to the canonical UPPERCASE form used to key
    immigration_requirements (Path A). Single seam for corridor keying."""
    if not raw:
        return ""
    return raw.strip().upper()
