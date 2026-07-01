#!/usr/bin/env python3
"""One-time offline geocoder for the living-areas + schools datasets.

Adds ``lat``/``lng`` to every neighborhood in ``living_areas.json`` and every
school in ``schools.json`` by geocoding ``"{name}, {city}"`` via Nominatim
(cached, >=1 req/sec per the usage policy). Idempotent: rows that already carry
finite ``lat``/``lng`` are skipped. Run once, review, commit the enriched files.

Usage (from repo root):
    python scripts/geocode_datasets.py            # geocode + write
    python scripts/geocode_datasets.py --check    # report coverage only, no writes
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Reuse the exact Nominatim geocoder the app uses (rate-limited, cached).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app.recommendations import geo  # noqa: E402

DATASETS_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "recommendations" / "datasets"
FILES = ["living_areas.json", "schools.json"]


def _has_coords(row: dict) -> bool:
    lat, lng = row.get("lat"), row.get("lng")
    return isinstance(lat, (int, float)) and isinstance(lng, (int, float))


def process(path: Path, *, write: bool) -> tuple[int, int, list[str]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    total = len(rows)
    missing: list[str] = []
    for row in rows:
        if _has_coords(row):
            continue
        query = f"{row.get('name', '')}, {row.get('city', '')}".strip(", ")
        coord = geo.geocode(query) if write else None
        if coord:
            row["lat"], row["lng"] = round(coord[0], 6), round(coord[1], 6)
            print(f"  ✓ {query} -> {row['lat']},{row['lng']}")
        else:
            missing.append(query or row.get("item_id", "?"))
            if write:
                print(f"  ✗ {query} -> NOT FOUND")
    if write:
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    have = sum(1 for r in rows if _has_coords(r))
    return total, have, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report coverage only, do not geocode/write")
    args = ap.parse_args()
    write = not args.check
    all_complete = True
    for name in FILES:
        path = DATASETS_DIR / name
        print(f"\n=== {name} ===")
        total, have, missing = process(path, write=write)
        pct = (have / total * 100) if total else 100.0
        print(f"  coverage: {have}/{total} ({pct:.0f}%)")
        if missing:
            all_complete = False
            print(f"  MISSING coords ({len(missing)}): {', '.join(missing)}")
    print("\n100% coverage." if all_complete else "\n⚠ Some rows lack coords — fix names or geocode manually before Phase 2.")
    return 0 if all_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
