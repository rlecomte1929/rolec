#!/usr/bin/env python3
"""
Report recommendations-catalog coverage for a destination city.

Examples
--------
    python scripts/recommendations_coverage.py Munich
    python scripts/recommendations_coverage.py "New York"
    python scripts/recommendations_coverage.py Tokyo --country Japan

Exits 0 if every category has at least MAX_ITEMS_PER_DESTINATION items;
exits 1 otherwise. Intended to be runnable both ad-hoc and from CI to
guard demo destinations against regressions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the backend package importable when invoked from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.services.catalog_coverage import (  # noqa: E402
    MAX_ITEMS_PER_DESTINATION,
    report_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination_city", help="Destination city (e.g. Munich)")
    parser.add_argument("--country", default=None, help="ISO/long country name (informational)")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-category lines; still emit the gap summary.",
    )
    args = parser.parse_args()

    coverage = report_coverage(args.destination_city)

    if not args.quiet:
        print(f"Catalog coverage for destination_city={args.destination_city!r}"
              + (f" country={args.country}" if args.country else ""))
        print(f"  target ≥ {MAX_ITEMS_PER_DESTINATION} items per category\n")
        col_key = max((len(k) for k in coverage), default=10)
        for key in sorted(coverage):
            data = coverage[key]
            items = data.get("items", 0)
            geo = "geo" if data.get("geo_bound") else "any"
            mark = "OK " if (isinstance(items, int) and items >= MAX_ITEMS_PER_DESTINATION) else "GAP"
            err = data.get("error")
            err_str = f"  {err}" if err else ""
            print(f"  {mark}  {key:<{col_key}}  {items:>3} items  ({geo}){err_str}")

    gaps = [k for k, d in coverage.items()
            if isinstance(d.get("items"), int)
            and (d.get("items") or 0) < MAX_ITEMS_PER_DESTINATION]
    print()
    if gaps:
        print(f"{len(gaps)} category gap(s) for {args.destination_city}: {', '.join(sorted(gaps))}")
        return 1
    print(f"All categories have ≥ {MAX_ITEMS_PER_DESTINATION} items for {args.destination_city}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
