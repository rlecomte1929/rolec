#!/usr/bin/env python3
"""
One-shot backfill: copy every recommendations dataset JSON into the
service_catalog_items master table (Phase 2a). Idempotent — re-running
re-syncs in place using (category, external_id) as the conflict key.

Usage:
    python scripts/backfill_master_catalog_from_json.py
    python scripts/backfill_master_catalog_from_json.py --dry-run
    python scripts/backfill_master_catalog_from_json.py --category schools
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.recommendations.registry import get_plugin, list_categories  # noqa: E402
from backend.services import service_catalog  # noqa: E402

# Per-category default country mapping for items whose JSON only carries `city`.
# Used so the master table has both city + country populated for downstream
# joins. Falls back to None when unknown.
_CITY_COUNTRY: Dict[str, str] = {
    "Singapore": "Singapore",
    "Oslo": "Norway",
    "New York": "United States",
    "San Francisco": "United States",
    "Munich": "Germany",
}


def _country_for(item: Dict[str, Any]) -> Optional[str]:
    if "country" in item and item["country"]:
        return str(item["country"])
    city = item.get("city")
    if city and city in _CITY_COUNTRY:
        return _CITY_COUNTRY[city]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print plan, write nothing.")
    parser.add_argument("--category", help="Backfill only this category key.")
    args = parser.parse_args()

    targets = list_categories()
    if args.category:
        targets = [c for c in targets if c["key"] == args.category]
        if not targets:
            print(f"No such category: {args.category}", file=sys.stderr)
            return 2

    total_inserted = 0
    total_updated = 0
    for cat in targets:
        key = cat["key"]
        plugin = get_plugin(key)
        if plugin is None:
            print(f"  SKIP {key:<22} no plugin")
            continue
        try:
            rows = plugin.load_dataset() or []
        except Exception as ex:  # pragma: no cover
            print(f"  ERR  {key:<22} load_dataset failed: {ex}")
            continue
        if not rows:
            print(f"  --   {key:<22} dataset empty")
            continue
        n_planned = len(rows)
        if args.dry_run:
            print(f"  PLAN {key:<22} would upsert {n_planned} items")
            continue

        n_done = 0
        for item in rows:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("item_id") or "").strip() or None
            name = str(item.get("name") or "").strip() or "(unnamed)"
            city = item.get("city")
            country = _country_for(item)
            # Strip the redundant fields from attributes_json since they're
            # promoted to columns; preserve the rest verbatim.
            attributes = {
                k: v for k, v in item.items()
                if k not in ("item_id", "name", "city", "country")
            }
            try:
                service_catalog.upsert_item(
                    category=key,
                    name=name,
                    attributes=attributes,
                    source="seed",
                    city=city,
                    country=country,
                    external_id=external_id,
                )
                n_done += 1
            except Exception as ex:  # pragma: no cover
                print(f"    ERR upsert {key}/{external_id or name}: {ex}")
        total_inserted += n_done
        print(f"  OK   {key:<22} upserted {n_done}/{n_planned}")

    print()
    if args.dry_run:
        print(f"Dry run — no writes. {len(targets)} categories planned.")
    else:
        print(f"Backfill done. {total_inserted} rows upserted across {len(targets)} categories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
