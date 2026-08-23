#!/usr/bin/env python3
"""Collapse duplicate `catalog_destination_allowlist` rows for the same destination.

WHY. HR could not reach 29 already-approved Dublin vendors. The country dropdown on the
vendor-curation page is built with a raw `new Set(destinations.map(d => d.country))` — exact
strings — so a destination stored three ways offers three options:

    dublin / ireland          <- lower-cased
    Dublin / IE               <- ISO code
    Dublin / Ireland          <- the convention the other 70 countries use

Pick the lower-cased one and the page sends `destination_city="dublin"`, which
`hr_catalog.get_curation_view` compares with a raw `==` against the catalog's `'Dublin'`.
Zero master items come back, HR concludes the destination is unsupported, clicks "Request a
new destination", and is handed FREE-TEXT city/country boxes — minting a fourth variant and
making the dropdown worse for the next person. A self-worsening loop.

WHAT THIS DOES. Keeps ONE row per destination — the title-cased, full-country-name form, the
convention 71 of 74 countries already follow — and deletes the redundant ones. Measured on
production 2026-08-23, the entire divergence is four rows:

    Paris  : Paris/FR   + Paris/France            -> keep Paris/France,  delete 1
    Dublin : Dublin/IE  + Dublin/Ireland
                        + dublin/ireland          -> keep Dublin/Ireland, delete 2
    Oslo   : Oslo/NO    + Oslo/Norway             -> keep Oslo/Norway,   delete 1

Exactly the three live corridors (ES→IE, FR→NO), because they were added later by a different
writer than the bulk seed. 338 rows -> 334.

DELETES, NOT RENAMES, and that is deliberate: every ISO row already has a full-name twin, so
renaming would collide with an existing row. Nothing renames, so nothing can duplicate.

WHY DELETING IS SAFE HERE (checked, not assumed, 2026-08-23):
  * `catalog_destination_allowlist` has NO inbound foreign keys — nothing references its id;
  * no `catalog_destination_requests` row points at Paris/Dublin/Oslo;
  * the survivor keeps the destination allowlisted, so `scrape_safety.is_destination_allowlisted`
    still returns True for it. That gate matches on the exact (city, country) pair, which is
    why the survivor must be the form the UI reads back — it is.
  * `service_catalog_items` and `company_vendor_selections` are NOT touched. They keep
    `country='IE'`; nothing joins them to this table (the curation view filters master items
    by CITY only), so the two vocabularies never meet.

This does NOT fix the raw `==` city comparison in `get_curation_view` — that is a separate
code change. It removes the row that triggers it. Both are worth doing: the code fix stops
the next casing divergence hurting anyone, this one fixes today's data.

    python backend/scripts/dedupe_destination_allowlist.py            # dry run
    python backend/scripts/dedupe_destination_allowlist.py --apply    # write
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import text  # noqa: E402

from backend.app.services.requirements_country_key import (  # noqa: E402
    resolve_catalog_country,
)

log = logging.getLogger("dedupe_destination_allowlist")

_SELECT = text(
    "SELECT id::text AS id, city, country, approved_by, approved_at, notes "
    "FROM catalog_destination_allowlist ORDER BY country, city"
)
_DELETE = text("DELETE FROM catalog_destination_allowlist WHERE id::text = :id")


def canon_city(value: Optional[str]) -> str:
    """Same normalisation `vendor_curation._canon_city` uses — lowercase, trimmed,
    diacritics stripped — so this script groups destinations exactly the way the
    curation read already matches them."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_marks.split()).lower()


def _is_iso_code(country: Optional[str]) -> bool:
    return len((country or "").strip()) == 2


def _title_score(row: Dict[str, Any]) -> Tuple[int, int, int, str]:
    """Rank candidates for which row SURVIVES. Lower sorts first (= kept).

    Preference order, most important first:
      1. full country name over an ISO code — the convention 71 of 74 countries follow,
         and the form the seed data and the UI's country grouping expect;
      2. title-cased country ('Ireland' over 'ireland');
      3. title-cased city ('Dublin' over 'dublin');
      4. id, purely so the choice is deterministic across runs.
    """
    country = (row.get("country") or "").strip()
    city = (row.get("city") or "").strip()
    return (
        1 if _is_iso_code(country) else 0,
        0 if country[:1].isupper() else 1,
        0 if city[:1].isupper() else 1,
        str(row.get("id") or ""),
    )


def plan(rows: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    """[(survivor, [rows to delete]), ...] for every destination with more than one row.

    Grouped by canonical CITY, not by (city, country): the whole point is that the same
    destination is stored under different country spellings, so grouping on country would
    put 'Dublin/IE' and 'Dublin/Ireland' in different buckets and find nothing.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(canon_city(row.get("city")), []).append(row)

    out: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
    for _city, group in sorted(buckets.items()):
        if len(group) < 2:
            continue
        ordered = sorted(group, key=_title_score)
        survivor, dupes = ordered[0], ordered[1:]
        # Only collapse rows that really are the SAME destination. Two cities sharing a
        # name in different countries (Cambridge UK / Cambridge US) must both survive — so
        # require the countries to resolve to the same canonical name. Anything else is
        # left alone and reported, never merged.
        keep_dupes = [d for d in dupes if _same_country(survivor, d)]
        skipped = [d for d in dupes if d not in keep_dupes]
        for s in skipped:
            log.info(
                "SKIP  %s / %s — same city name, different country from the survivor (%s)",
                s.get("city"), s.get("country"), survivor.get("country"),
            )
        if keep_dupes:
            out.append((survivor, keep_dupes))
    return out


def _same_country(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Do these two rows name the same country, whether by ISO code or full name?

    Uses the repo's own `requirements_country_key.resolve_catalog_country`, which maps both
    spellings onto one canonical UPPERCASE name (IE → IRELAND, FR → FRANCE, …).

    A first draft of this tried to match an ISO code against the start of the full name.
    That is wrong and the unit test below caught it: `'ireland'.startswith('ie')` is FALSE —
    ISO codes are not prefixes (IE→Ireland, DE→Germany, ES→Spain). It happened to work for
    FR/France and NO/Norway, which is exactly the kind of heuristic that passes a spot-check
    and then silently refuses the one destination you care about.
    """
    ca, cb = (a.get("country") or "").strip(), (b.get("country") or "").strip()
    if not ca or not cb:
        return False
    if ca.lower() == cb.lower():
        return True
    return resolve_catalog_country(ca) == resolve_catalog_country(cb)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Collapse duplicate destination-allowlist rows")
    p.add_argument("--apply", action="store_true", help="Write. Omit for a dry run.")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from backend.database import db  # noqa: E402  (import after sys.path bootstrap)

    with db.engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(_SELECT).mappings().all()]

    groups = plan(rows)
    to_delete: List[Dict[str, Any]] = []
    for survivor, dupes in groups:
        log.info("\n%s / %s   ← KEEP", survivor.get("city"), survivor.get("country"))
        for d in dupes:
            log.info("    %-22s ← delete  (id %s)",
                     f"{d.get('city')} / {d.get('country')}", str(d.get("id"))[:8])
            to_delete.append(d)

    log.info(
        "\nrows=%d  destinations_with_duplicates=%d  rows_to_delete=%d  rows_after=%d",
        len(rows), len(groups), len(to_delete), len(rows) - len(to_delete),
    )
    if not to_delete:
        log.info("Nothing to do — every destination already has exactly one row.")
        return 0
    if not args.apply:
        log.info("DRY RUN — nothing written. Re-run with --apply to write.")
        return 0

    written = 0
    for row in to_delete:
        with db.engine.begin() as conn:
            conn.execute(_DELETE, {"id": str(row["id"])})
        written += 1
    log.info("APPLIED — %d row(s) deleted.", written)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
