#!/usr/bin/env python3
"""
[AIQ-1788] Stage a registry harvest CSV into vendor_candidates.

Every row lands `status='pending'`. Nothing here creates a supplier, and nothing becomes
visible to an employee — promotion is a human decision behind the admin review surface.

Run from the repo root:

    # preview — reads and decides everything, writes nothing
    python scripts/import_supplier_candidates.py audos-workspace-776786/data/card-c-harvest.csv

    # write
    python scripts/import_supplier_candidates.py <csv> --apply

Dry run is the DEFAULT and takes the same code path as a real run, so its numbers are the
numbers you will get. Exits non-zero if any row was rejected, unless --allow-rejections:
the reject list is the re-sourcing worklist, and a silent partial import is how you end up
believing you have coverage you do not.

Reads DATABASE_URL. Point it at a throwaway database first if you want to see the rows.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.suppliers.executor import stage, summarise      # noqa: E402
from backend.imports.suppliers.parsers import RowError, read_csv     # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="harvest CSV (see EXPECTED_HEADER in parsers.py)")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument(
        "--allow-rejections",
        action="store_true",
        help="exit 0 even when rows were rejected (do not use in a pipeline)",
    )
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"✖ no such file: {args.csv}")
        return 2

    try:
        candidates = list(read_csv(args.csv))
    except RowError as exc:
        print(f"✖ {args.csv}: {exc}")
        return 2

    print(f"read {len(candidates)} row(s) from {args.csv}\n")

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set — even a dry run reads suppliers + "
              "vendor_candidates to decide what is a duplicate")
        return 2

    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True)
    mode = "APPLY" if args.apply else "DRY RUN — nothing will be written"
    print(f"mode: {mode}\n")

    # One transaction for the whole import: a failure halfway through must not leave one
    # corridor staged and the next missing.
    with engine.begin() as conn:
        results, rejections = stage(conn, candidates, dry_run=not args.apply)
        print(summarise(results, rejections))
        if not args.apply:
            conn.rollback()

    if rejections and not args.allow_rejections:
        print(f"\n✖ {len(rejections)} row(s) rejected — nothing about them was staged.")
        print("  Re-source them against a real register, or re-run with --allow-rejections")
        print("  to stage only the rows that passed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
