#!/usr/bin/env python3
"""Load an Otto immigration-research JSONL deliverable into `otto_staging`.

This replaces browser-scraping Otto's chat thread, which capped out: the France batch of
2026-08-11 loaded 24 of 109 facts and `load_log` recorded *"85 facts unreachable via browser
(systemic capture ceiling on large threads)"*. Otto writes a file into the synced workspace
instead, the `[audos-sync]` bot commits it, and this reads it. Same route the vendor harvest
already takes (`scripts/import_supplier_candidates.py`).

Run from the repo root:

    # preview — reads, validates and decides everything, writes nothing
    python scripts/import_otto_facts.py FR-immig-2026-08-11

    # write
    python scripts/import_otto_facts.py FR-immig-2026-08-11 --apply \\
        --source-label "France Immigration Research"

Dry run is the DEFAULT and takes the same code path as a real run, so its numbers are the
numbers you will get. Exits non-zero if any row was rejected on sourcing, unless
--allow-rejections: the reject list is the re-sourcing worklist, and a silent partial import
is how you end up believing you have coverage you do not.

Accepts a bare batch id and finds the file itself, **including at the doubled path**. Otto
writes to `audos-workspace-776786/data/…` from inside a workspace whose root already maps to
`audos-workspace-776786/`, so files arrive at
`audos-workspace-776786/audos-workspace-776786/data/…`. Per `docs/audos-card-contract.md:148`
that doubling "wasted the most time, so check it first" — so this checks it for you.

Reads DATABASE_URL. Point it at a throwaway database first if you want to see the rows.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.otto.executor import (          # noqa: E402
    PASS,
    queue_expected,
    reconcile,
    stage,
    summarise,
)
from backend.imports.otto.parsers import FactRowError, read_jsonl   # noqa: E402

WORKSPACE = "audos-workspace-776786"


def candidate_paths(arg: str) -> List[Path]:
    """Every place the named deliverable could plausibly be, most likely first."""
    given = Path(arg)
    stem = given.name if given.suffix else f"{given.name}.jsonl"
    return [
        given,
        REPO_ROOT / WORKSPACE / "data" / stem,
        REPO_ROOT / WORKSPACE / WORKSPACE / "data" / stem,   # the doubled path — see docstring
    ]


def resolve(arg: str) -> Optional[Path]:
    for path in candidate_paths(arg):
        if path.is_file():
            return path
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="batch id (e.g. FR-immig-2026-08-11) or a path to the JSONL")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--batch-id", help="override the batch id (default: the file's stem)")
    ap.add_argument(
        "--source-label",
        help="processing_queue.source_label this deliverable answers, e.g. "
             "'France Immigration Research'. Defaults to the batch id. The queue row is where "
             "expected_count comes from, so without a match completeness cannot be proven.",
    )
    ap.add_argument(
        "--expected",
        type=int,
        help="expected fact count, when processing_queue has none. A batch with no expected "
             "count can never report 'pass' — an unknown denominator is a reason to withhold "
             "success, not to assume it.",
    )
    ap.add_argument(
        "--allow-rejections",
        action="store_true",
        help="exit 0 even when rows were rejected on sourcing (do not use in a pipeline)",
    )
    args = ap.parse_args()

    path = resolve(args.target)
    if path is None:
        print(f"✖ no such deliverable: {args.target}")
        print("  looked in:")
        for cand in candidate_paths(args.target):
            print(f"    - {cand}")
        print("\n  If Otto reported writing this file, it is not there. That is the failure")
        print("  class in docs/audos-card-contract.md:195 — the artifact is claimed and the")
        print("  check that would catch its absence was never run. Re-issue the card.")
        return 2

    batch_id = args.batch_id or path.stem
    source_label = args.source_label or batch_id

    try:
        rows, rejections = read_jsonl(path, batch_id=batch_id)
    except FactRowError as exc:
        print(f"✖ {path}: {exc}")
        return 2

    print(f"read {len(rows) + len(rejections)} record(s) from {path}")
    print(f"batch: {batch_id!r}   source_label: {source_label!r}\n")

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set — even a dry run reads immigration_fact_candidates "
              "to decide what is already present")
        return 2

    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True)
    print(f"mode: {'APPLY' if args.apply else 'DRY RUN — nothing will be written'}\n")

    # One transaction for the whole batch: a failure halfway must not leave a country
    # half-loaded with a ledger row claiming otherwise.
    with engine.begin() as conn:
        expected = args.expected
        if expected is None:
            expected = queue_expected(conn, source_label)
            if expected is None:
                print(f"⚠ processing_queue has no row for source_label {source_label!r} and "
                      "--expected was not given.")
                print("  This batch cannot report 'pass'. Pass --source-label or --expected "
                      "to prove completeness.\n")

        result = stage(conn, rows, rejections=rejections, dry_run=not args.apply)
        ledger = reconcile(
            conn,
            result,
            source_label=source_label,
            expected_count=expected,
            dry_run=not args.apply,
        )
        print(summarise(result, ledger))
        if not args.apply:
            print("\n  (preview — pass --apply to write, including the load_log row)")
            conn.rollback()

    if rejections and not args.allow_rejections:
        print(f"\n✖ {len(rejections)} row(s) rejected — nothing about them was staged.")
        print("  Re-source them against an official publisher, or re-run with")
        print("  --allow-rejections to stage only the rows that passed.")
        return 1
    if ledger["reconcile_status"] != PASS:
        # Not an error — a partial load is a legitimate outcome. But it must not exit 0 into a
        # script that would read that as "batch complete" and close the queue row.
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
