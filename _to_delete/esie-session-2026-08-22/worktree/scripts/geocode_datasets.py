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
import re
import sys
from pathlib import Path

# Reuse the exact Nominatim geocoder the app uses (rate-limited, cached).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app.recommendations import geo  # noqa: E402

DATASETS_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "recommendations" / "datasets"
FILES = ["living_areas.json", "schools.json"]

# Manual, approximate campus coordinates for seed schools Nominatim can't resolve
# by name. Approximate-but-in-the-right-area is acceptable here: these feed a
# best-effort "reachable from neighborhood" proximity join over representative
# seed data, not authoritative routing.
_MANUAL_COORDS: dict[tuple[str, str], tuple[float, float]] = {
    ("Dover Court Preparatory", "Singapore"): (1.3067, 103.7847),
    ("British International School Oslo", "Oslo"): (59.9139, 10.7360),
    ("Lycée Français René Cassin", "Oslo"): (59.9210, 10.6800),
    ("International School of the Peninsula", "San Francisco"): (37.4280, -122.1450),
    ("British International School of New York", "New York"): (40.7380, -73.9740),
    ("Avenues: The World School", "New York"): (40.7480, -74.0040),
    ("St. George's International (Munich)", "Munich"): (48.1500, 11.5550),
}


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
        name = str(row.get("name", ""))
        city = str(row.get("city", ""))
        override = _MANUAL_COORDS.get((name, city))
        if override and write:
            row["lat"], row["lng"] = round(override[0], 6), round(override[1], 6)
            print(f"  ✓ (manual) {name}, {city} -> {row['lat']},{row['lng']}")
            continue
        # Try the full name, then a cleaned variant (drop "(ACRONYM)" and colons)
        # — many international-school names don't resolve verbatim in Nominatim.
        cleaned = re.sub(r"\s*\([^)]*\)", "", name).replace(":", "").strip()
        candidates = [f"{name}, {city}"]
        if cleaned and cleaned != name:
            candidates.append(f"{cleaned}, {city}")
        query = candidates[0].strip(", ")
        coord = None
        if write:
            for q in candidates:
                coord = geo.geocode(q.strip(", "))
                if coord:
                    query = q.strip(", ")
                    break
        if coord:
            row["lat"], row["lng"] = round(coord[0], 6), round(coord[1], 6)
            print(f"  ✓ {query} -> {row['lat']},{row['lng']}")
        else:
            missing.append(f"{name}, {city}")
            if write:
                print(f"  ✗ {name}, {city} -> NOT FOUND")
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
