#!/usr/bin/env python3
"""
Seed the master catalog for a destination via the LLM scraper (Phase 2b).

The same entry point that gets called automatically when a new case lands
on a destination with gaps. Useful to kick off ahead of time, or to backfill
specific categories that the auto-trigger missed.

Examples
--------
    # All categories that have < 10 master items for Munich
    CATALOG_SCRAPER_ENABLED=1 OPENAI_API_KEY=sk-... \\
      python scripts/seed_destination.py Munich --country Germany

    # Single category
    python scripts/seed_destination.py Tokyo --category schools --country Japan

Requires: CATALOG_SCRAPER_ENABLED=1 + OPENAI_API_KEY in env. Otherwise the
underlying scraper is a no-op (by design — never burn credits accidentally).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.services.catalog_coverage import (  # noqa: E402
    MAX_ITEMS_PER_DESTINATION,
    categories_with_gaps,
    ensure_destination_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination_city")
    parser.add_argument("--country", default=None)
    parser.add_argument(
        "--category",
        default=None,
        help="If set, only populate this category. Otherwise: every category with a gap.",
    )
    args = parser.parse_args()

    targets = [args.category] if args.category else categories_with_gaps(args.destination_city)
    if not targets:
        print(f"No gap categories for {args.destination_city}; nothing to do.")
        return 0

    print(f"Seeding {len(targets)} category gap(s) for {args.destination_city}"
          + (f" ({args.country})" if args.country else "") + ":\n")
    grand_total = 0
    for cat in targets:
        result = ensure_destination_catalog(
            category=cat,
            destination_city=args.destination_city,
            country=args.country,
        )
        inserted = result.get("scraper_inserted", 0) or 0
        dispatched = "yes" if result.get("scraper_dispatched") else "skipped"
        print(
            f"  {cat:<22} have={result.get('have'):>2}  "
            f"needed={result.get('needed'):>2}  "
            f"inserted={inserted:>2}  scraper={dispatched}"
        )
        grand_total += inserted

    print()
    if grand_total == 0:
        print(
            "0 rows inserted. Check that CATALOG_SCRAPER_ENABLED=1 and "
            "OPENAI_API_KEY is set in the environment running the backend."
        )
        return 1
    print(f"Inserted {grand_total} master rows across {len(targets)} categories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
