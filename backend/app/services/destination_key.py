"""Canonical identity for a (city, country) destination — ONE definition, used by
both sides of every comparison.

WHY THIS EXISTS. `catalog_destination_allowlist` stores 70 FULL country names
('France'); `catalog_employee_demand` stores ONLY ISO-2 ('FR'). A raw `=` between
them can never match, so every demand gap read `allowlisted:false`, and every
"Allowlist & scrape" click minted a SECOND row for a destination that was already
approved. PR #2020 deleted four such rows; the writer was never fixed, so they came
back on the next click — `backend/scripts/dedupe_destination_allowlist.py` says as
much in its own header.

Measured on production 2026-08-23: the allowlist held 70 country names and zero
ISO-2 codes; the demand table held eight ISO-2 codes and zero names. The two sets
are disjoint, so the failure was total, not occasional.

A LEAF MODULE ON PURPOSE. `scrape_safety` is the L4 safety gate; it must not import
the HR curation layer to borrow a string helper. This module imports nothing but the
stdlib and the repo's designated country resolver, so the gate, the curation read and
the dedupe script can all share one definition without a cycle.

The city half is character-for-character the same normalisation as
`vendor_curation._canon_city` and the frontend's `canonPlace()`
(frontend/src/components/location/index.tsx), so the UI, the curation matcher and this
gate agree on what counts as one place.
"""
from __future__ import annotations

import unicodedata
from typing import Optional, Set, Tuple

from .requirements_country_key import to_iso_alpha2

# ("iso", canon_city, "FR")  or  ("raw", canon_city, folded_literal_country)
DestinationKey = Tuple[str, str, str]


def canon_city(value: Optional[str]) -> str:
    """Lowercase, whitespace-collapsed, diacritic-folded key for a place name.

    NFKD -> drop combining marks -> collapse+trim whitespace -> lowercase.

    `.lower()`, deliberately NOT `.casefold()`. Casefold maps 'ß' to 'ss', which would
    merge Weissenburg and Weißenburg into one destination. Widening this key widens a
    SAFETY gate, so it stays exactly as wide as the matcher that already ships.

    Returns "" for None/empty/whitespace-only — an unusable key, never a matchable one.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_marks.split()).lower()


def canon_country(value: Optional[str]) -> Optional[str]:
    """ISO 3166-1 alpha-2 UPPERCASE, or None when genuinely unresolvable.

    A deliberate one-line wrapper so this file has exactly one country resolver and a
    caller cannot reach for a neighbour by mistake:
      * `to_iso` is NARROW — it answers "do we hold requirement CATALOG data?" and
        returns None for countries we serve perfectly well.
      * `iso_to_catalog_name` uses a DIFFERENT convention ('FRANCE'), not the
        allowlist's ('France').
    """
    if value is None:
        return None
    return to_iso_alpha2(str(value).strip())


def destination_keys(city: Optional[str], country: Optional[str]) -> Set[DestinationKey]:
    """Every canonical key this (city, country) answers to.

    An EMPTY set is the fail-closed sentinel: a probe with no keys matches nothing, and
    a stored row with no keys is never indexed — so a junk row ('', '') can never
    allowlist anything.

    TWO key shapes, and the second is load-bearing:

      ("iso", city, "FR")   Emitted ONLY when the country resolves. This is the key
          that reconciles the two vocabularies, and the entire point of the fix.

      ("raw", city, "france")   The folded LITERAL country, ALWAYS emitted. This exists
          so that canonicalising can never REMOVE an existing allowlisted destination.
          The name map does not cover every country in the allowlist (Kazakhstan,
          Uzbekistan, Trinidad and Tobago, ...); under an ISO-only index those rows
          would silently drop out and a destination an admin explicitly approved would
          stop scraping. Folding one country string against itself can never merge two
          different countries, so this key adds no reach beyond case/whitespace/accents.

    The gate is therefore OLD UNION NEW — never NEW alone.
    """
    c = canon_city(city)
    if not c:
        return set()
    literal = canon_city(country)  # fold the country STRING; no ISO involved
    if not literal:
        return set()
    keys: Set[DestinationKey] = {("raw", c, literal)}
    iso = canon_country(country)
    if iso:
        keys.add(("iso", c, iso))
    return keys
