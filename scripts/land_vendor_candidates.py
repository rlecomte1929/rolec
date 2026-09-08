#!/usr/bin/env python3
"""Stage a harvest CSV and promote ONLY the runs this invocation just staged.

``scripts/import_supplier_candidates.py`` has an unscoped promote flag that calls
``executor.promote()`` with no ``run_ids``, which promotes every unpromoted pending/duplicate
candidate in the table.
Measured 2026-08-13: that previewed as 235 suppliers for a 16-row harvest. This helper is
the scoped path: ``stage()`` first, then ``promote(session, run_ids=[those], dry_run=…)``.

    python scripts/land_vendor_candidates.py harvest.csv           # dry run (default)
    python scripts/land_vendor_candidates.py harvest.csv --apply   # write

This CLI has no unscoped promote flag. Promotion is what this script is for, and it is
always scoped. Default is dry_run; ``--apply`` writes both the staging rows and the unvetted
suppliers (``platform_vetting_status='pending'``).
"""
from __future__ import annotations

import argparse
import inspect
import os
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.vendor_harvester import Candidate, PairResult  # noqa: E402
from backend.imports.suppliers.executor import promote, stage, summarise  # noqa: E402
from backend.imports.suppliers.parsers import RowError, read_csv  # noqa: E402

StageFn = Callable[..., Tuple[List[PairResult], List[str]]]
PromoteFn = Callable[..., Tuple[int, int, List[str]]]


def run_ids_from(results: Sequence[PairResult]) -> List[str]:
    """Every run_id stage() assigned. Empty on a dry-run stage (nothing was written)."""
    ids: List[str] = []
    for result in results:
        rid = getattr(result, "run_id", None)
        if rid:
            ids.append(str(rid))
    return ids


def land(
    candidates: Sequence[Candidate],
    conn: Any,
    session: Any,
    *,
    dry_run: bool,
    stage_fn: StageFn = stage,
    promote_fn: PromoteFn = promote,
) -> Tuple[List[PairResult], List[str], List[str], Tuple[int, int, List[str]]]:
    """Stage, then promote strictly those runs. ``promote_fn`` is always called with run_ids."""
    sig = inspect.signature(promote_fn)
    if "run_ids" not in sig.parameters:
        raise RuntimeError("promote() must accept run_ids — refusing an unscoped promoter")

    results, rejections = stage_fn(conn, candidates, dry_run=dry_run)
    run_ids = run_ids_from(results)
    # Always pass run_ids, even when the list is empty (dry-run stage writes no runs).
    # An omitted kwarg is the unscoped landmine this helper exists to avoid.
    promoted = promote_fn(session, dry_run=dry_run, run_ids=run_ids)
    return results, rejections, run_ids, promoted


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="harvest CSV (see EXPECTED_HEADER in parsers.py)")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument(
        "--allow-rejections",
        action="store_true",
        help="exit 0 even when rows were rejected (do not use in a pipeline)",
    )
    args = ap.parse_args(argv)

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
        print(
            "✖ DATABASE_URL is not set — even a dry run reads suppliers + "
            "vendor_candidates to decide what is a duplicate"
        )
        return 2

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, future=True)
    dry_run = not args.apply
    mode = "APPLY" if args.apply else "DRY RUN — nothing will be written"
    print(f"mode: {mode}\n")

    # Stage and promote are separate transactions: supplier_registry.create_supplier
    # commits internally, so promotion cannot share the staging connection. Commit
    # staging first so promote(run_ids=…) can see the rows. Dry-run rolls the stage back
    # and still calls promote with run_ids (empty, because a dry-run stage writes none).
    Session = sessionmaker(bind=engine)
    with engine.begin() as conn:
        results, rejections = stage(conn, candidates, dry_run=dry_run)
        run_ids = run_ids_from(results)
        if dry_run:
            conn.rollback()

    with Session() as session:
        # Always pass run_ids. Never call promote() unscoped.
        promo = promote(session, dry_run=dry_run, run_ids=run_ids)
        if dry_run:
            session.rollback()

    print(summarise(results, rejections))
    print()
    n, skipped, problems = promo
    print(
        f"promote:    {n} supplier(s) -> vetting queue "
        f"(platform_vetting_status='pending')  run_ids={run_ids or '(none yet)'}"
    )
    if skipped:
        print(f"  skipped:  {skipped}")
        for problem in problems:
            print(f"    - {problem}")
    if dry_run:
        print("  (preview — pass --apply to write)")

    if rejections and not args.allow_rejections:
        print(f"\n✖ {len(rejections)} row(s) rejected — nothing about them was staged.")
        print("  Re-source them against a real register, or re-run with --allow-rejections")
        print("  to stage only the rows that passed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
