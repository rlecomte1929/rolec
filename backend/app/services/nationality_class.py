"""Nationality class for a (nationality, destination) pair.

The requirements engine had no nationality dimension, so a case's destination
alone selected the requirement set. `requirement_items` for FRANCE is the
non-EEA salaried route (VLS-TS / ANEF / DGEF) — its own seed file says so:
"EEA/EU nationals have free movement and need none of this." Without a way to
express that, the engine served a French citizen relocating home the full French
work-visa track. This module supplies the missing dimension.

Three classes:

  OWN_NATIONAL  — a national of the destination returning/moving home.
  EU_EEA        — free movement into the destination applies.
  THIRD_COUNTRY — no free movement; the visa/permit track applies.

`classify` returns ``None`` when either side is unrecognised. That is deliberate
and asymmetric: we suppress a requirement only when we POSITIVELY know free
movement applies. An unknown nationality keeps the full requirement list and
makes no claim in either direction — the failure mode we must never have is a
fabricated "nothing required".
"""
from __future__ import annotations

from typing import Optional

from .requirements_country_key import to_iso

OWN_NATIONAL = "OWN_NATIONAL"
EU_EEA = "EU_EEA"
THIRD_COUNTRY = "THIRD_COUNTRY"

# EU-27.
_EU = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
}

# EEA = EU + Iceland, Liechtenstein, Norway. Norway being EEA-but-NOT-EU is the
# trap this codebase keeps hitting (customs union, corridor content) — it is
# spelled out here rather than inferred.
_EEA = _EU | {"IS", "LI", "NO"}

# Switzerland is neither EU nor EEA, but Swiss nationals hold equivalent free
# movement under the EU–Swiss Agreement on the Free Movement of Persons (AFMP).
# Classifying CH as THIRD_COUNTRY would reproduce the exact bug this module
# exists to fix, so it is included in the free-movement set — by a different
# legal instrument, hence the separate constant.
_FREE_MOVEMENT = _EEA | {"CH"}

# Nationality is stored free-text and is often adjectival. `to_iso` already
# handles ISO codes, aliases and full country names; these cover the rest.
_ADJECTIVAL = {
    "FRENCH": "FR",
    "NORWEGIAN": "NO",
    "SWEDISH": "SE",
    "GERMAN": "DE",
    "DUTCH": "NL",
    "BRITISH": "GB",
    "AMERICAN": "US",
    "INDIAN": "IN",
    "SINGAPOREAN": "SG",
    "SWISS": "CH",
}


def _nationality_to_iso(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None
    if s in _ADJECTIVAL:
        return _ADJECTIVAL[s]
    iso = to_iso(s)
    if iso:
        return iso
    # `to_iso` only knows the seeded DESTINATIONS, but nationality ranges over
    # every country. Accept any bare alpha-2 code. An unrecognised one falls
    # through to THIRD_COUNTRY — i.e. the full visa list, which is exactly
    # today's behaviour, so an unknown code can never produce a false
    # "nothing required".
    if len(s) == 2 and s.isalpha():
        return s
    return None


def classify(nationality: Optional[str], dest_country: Optional[str]) -> Optional[str]:
    """Classify a nationality against a destination.

    Returns OWN_NATIONAL, EU_EEA, THIRD_COUNTRY, or None when either side is
    unrecognised (caller must then not filter and not claim).
    """
    nat = _nationality_to_iso(nationality)
    dest = to_iso(dest_country)
    if not nat or not dest:
        return None
    if nat == dest:
        return OWN_NATIONAL
    # Free movement only buys you something when the destination is itself inside
    # the free-movement area. An EU passport is worth nothing at the US border.
    if dest in _EEA and nat in _FREE_MOVEMENT:
        return EU_EEA
    return THIRD_COUNTRY
