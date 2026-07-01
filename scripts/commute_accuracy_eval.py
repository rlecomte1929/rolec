#!/usr/bin/env python3
"""Phase 1 commute-accuracy harness for the living-areas straight-line model.

Compares the app's straight-line-plus-speed commute estimate against a set of
reference transit times per city, reports mean absolute error (MAE) and the
share of pairs within ±10 minutes, and sweeps ``road_factor`` to find the best
fit. Run from repo root:

    python scripts/commute_accuracy_eval.py

IMPORTANT — reference values: the ``ref_min`` transit times below are
**manual real-world approximations** (author-estimated from city geography),
NOT pulled from the Google Maps API. They exist so the harness is runnable
today; for authoritative validation, replace them with real Google Maps transit
directions for each (office → neighborhood) pair (a key wires into geo.py's
``commute_minutes`` provider seam), then re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app.recommendations import geo  # noqa: E402

DATASET = Path(__file__).resolve().parent.parent / "backend" / "app" / "recommendations" / "datasets" / "living_areas.json"

# Representative destination-city office anchors (approx coords of a common CBD).
OFFICES: dict[str, tuple[float, float]] = {
    "Singapore": (1.2839, 103.8515),      # Raffles Place / CBD
    "New York": (40.7549, -73.9840),      # Midtown (Bryant Park)
    "Munich": (48.1372, 11.5755),         # Marienplatz
    "Oslo": (59.9110, 10.7500),           # Sentrum / Oslo S
    "San Francisco": (37.7946, -122.3999),  # Financial District
}

# (city, neighborhood name, reference transit minutes — APPROX, not Google API)
REFERENCE_PAIRS: list[tuple[str, str, int]] = [
    ("Singapore", "Tiong Bahru", 10), ("Singapore", "Holland Village", 20),
    ("Singapore", "Serangoon", 25), ("Singapore", "Katong", 22), ("Singapore", "Novena", 15),
    ("New York", "Upper East Side", 16), ("New York", "Upper West Side", 15),
    ("New York", "Williamsburg", 25), ("New York", "Astoria", 27), ("New York", "Brooklyn Heights", 22),
    ("Munich", "Schwabing", 12), ("Munich", "Maxvorstadt", 8),
    ("Munich", "Haidhausen", 11), ("Munich", "Pasing", 22),
    ("Oslo", "Frogner", 12), ("Oslo", "Grünerløkka", 11), ("Oslo", "Sagene", 15),
    ("San Francisco", "SOMA", 8), ("San Francisco", "Mission District", 20),
    ("San Francisco", "Pacific Heights", 20),
]


def _coord_index() -> dict[tuple[str, str], tuple[float, float]]:
    rows = json.loads(DATASET.read_text(encoding="utf-8"))
    idx: dict[tuple[str, str], tuple[float, float]] = {}
    for r in rows:
        if isinstance(r.get("lat"), (int, float)) and isinstance(r.get("lng"), (int, float)):
            idx[(r["city"], r["name"])] = (r["lat"], r["lng"])
    return idx


def _evaluate(road_factor: float, idx) -> tuple[float, float, list]:
    rows = []
    errs = []
    for city, name, ref in REFERENCE_PAIRS:
        area = idx.get((city, name))
        office = OFFICES.get(city)
        if not area or not office:
            continue
        est = geo.straight_line_commute_minutes(office, area, "transit", road_factor)
        if est is None:
            continue
        est_r = round(est)
        err = abs(est_r - ref)
        errs.append(err)
        rows.append((city, name, ref, est_r, err))
    if not errs:
        return 0.0, 0.0, rows
    mae = sum(errs) / len(errs)
    within10 = 100.0 * sum(1 for e in errs if e <= 10) / len(errs)
    return mae, within10, rows


def main() -> int:
    idx = _coord_index()

    # road_factor sweep
    print("=== road_factor sweep (transit) ===")
    best = (None, 1e9)
    for rf in [1.0, 1.15, 1.3, 1.45, 1.6, 1.75, 1.9]:
        mae, within10, _ = _evaluate(rf, idx)
        print(f"  road_factor={rf:<4}  MAE={mae:5.1f} min   within±10min={within10:4.0f}%")
        if mae < best[1]:
            best = (rf, mae)

    rf = geo.DEFAULT_ROAD_FACTOR
    mae, within10, rows = _evaluate(rf, idx)
    print(f"\n=== per-pair detail at shipped road_factor={rf} ===")
    print(f"{'city':<14}{'neighborhood':<20}{'ref':>5}{'est':>5}{'err':>5}")
    for city, name, ref, est, err in sorted(rows, key=lambda r: -r[4]):
        flag = "  <-- >10" if err > 10 else ""
        print(f"{city:<14}{name:<20}{ref:>5}{est:>5}{err:>5}{flag}")

    print(f"\nMAE={mae:.1f} min · within±10min={within10:.0f}% · n={len(rows)}")
    print(f"Bar: ±10 min for 80% of pairs -> {'PASS' if within10 >= 80 else 'FAIL'}")
    print(f"Best-fit road_factor in sweep: {best[0]} (MAE {best[1]:.1f})")
    print("\nNOTE: reference times are manual approximations, not Google Maps API pulls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
