"""Seed the Supplier Registry by running vendor discovery over the priority corridors (VEN-09).

Usage:
    python -m backend.scripts.seed_priority_corridors --dry-run          # preview cells, no calls
    python -m backend.scripts.seed_priority_corridors                    # run (provider must be configured)
    python -m backend.scripts.seed_priority_corridors --category movers --max-cells 5

Iterates PRIORITY_CORRIDORS × SERVICE_CATEGORY_SEARCH_TERMS and calls the discovery
orchestrator for each (category, destination-city) cell. Discovered vendors land in
`suppliers` as PENDING (admin vetting queue).

COST SAFETY: a no-op unless a provider is configured (DISCOVERY_PROVIDER + key). Each
cell is one paid provider search, so use --category / --max-cells to bound a run, and
--dry-run to preview first. Off by default across the platform.
"""
from __future__ import annotations

import argparse
import logging

from backend.app.config.vendor_discovery import PRIORITY_CORRIDORS, SERVICE_CATEGORY_SEARCH_TERMS
from backend.app.services import maps_discovery
from backend.app.services.vendor_discovery.orchestrator import discover_and_store_vendors

log = logging.getLogger(__name__)


def run(*, category: str | None = None, max_cells: int = 0, dry_run: bool = False) -> dict:
    """Iterate corridor × category cells. Returns {cells, imported}."""
    categories = [category] if category else list(SERVICE_CATEGORY_SEARCH_TERMS.keys())
    # Unique destination (city, country) pairs from the corridors.
    dests = []
    seen = set()
    for c in PRIORITY_CORRIDORS:
        key = (c["destination_city"], c["destination_country"])
        if key not in seen:
            seen.add(key)
            dests.append(key)

    status = maps_discovery.provider_status()
    if not dry_run and not status["configured"]:
        log.warning("Discovery provider not configured (provider=%s) — nothing to do. "
                    "Set DISCOVERY_PROVIDER + API key to enable.", status["provider"])
        return {"cells": 0, "imported": 0}

    cells = 0
    imported = 0
    for city, country in dests:
        for cat in categories:
            if max_cells and cells >= max_cells:
                log.info("Reached --max-cells=%d; stopping.", max_cells)
                return {"cells": cells, "imported": imported}
            cells += 1
            if dry_run:
                log.info("[dry-run] would discover %s / %s (%s)", cat, city, country)
                continue
            got = discover_and_store_vendors(cat, city, country)
            imported += len(got)
    return {"cells": cells, "imported": imported}


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Seed suppliers via vendor discovery over priority corridors.")
    parser.add_argument("--category", default=None, help="Limit to one service_category slug.")
    parser.add_argument("--max-cells", type=int, default=0, help="Cap the number of (category, city) cells (0 = all).")
    parser.add_argument("--dry-run", action="store_true", help="Preview cells without any provider calls or writes.")
    args = parser.parse_args(argv)
    result = run(category=args.category, max_cells=args.max_cells, dry_run=args.dry_run)
    log.info("%s: %d cells, %d vendors imported (pending)",
             "DRY-RUN" if args.dry_run else "DONE", result["cells"], result["imported"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
