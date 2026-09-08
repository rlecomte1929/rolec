#!/usr/bin/env python3
"""Backfill immigration_milestones for a case from its corridor template (DOC-4).

Dry-run by DEFAULT (prints the rows it would insert, writes nothing). Pass --apply to write.
Idempotent: an already-seeded case is skipped unless --force.

    python backend/scripts/seed_case_milestones.py --case-id <id> --from ES --to IE \\
        [--org-id <id>] [--move-date 2026-10-01] [--apply] [--force]

Reads DATABASE_URL via the app db engine. Point it at a throwaway DB first if unsure.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.immigration_milestone_seed import (  # noqa: E402
    build_milestone_rows,
    get_template,
    seed_case_milestones,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--from", dest="corridor_from", required=True)
    ap.add_argument("--to", dest="corridor_to", required=True)
    ap.add_argument("--org-id", default=None)
    ap.add_argument("--move-date", default=None, help="ISO date; target_dates are computed from it")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if not get_template(args.corridor_from, args.corridor_to):
        print(f"No milestone template for {args.corridor_from}->{args.corridor_to}. Nothing to do.")
        return 0
    move = date.fromisoformat(args.move_date) if args.move_date else None
    rows = build_milestone_rows(args.case_id, args.org_id, args.corridor_from,
                                args.corridor_to, move, datetime.utcnow())
    print(f"{len(rows)} milestone(s) for case {args.case_id} ({args.corridor_from}->{args.corridor_to}):")
    for r in rows:
        print(f"  {r['sort_order']:>2}. {r['milestone_type']:<34} target={r['target_date']} book_early={r['book_early_alert']}")
    if not args.apply:
        print("\nDRY RUN — no rows written. Re-run with --apply to write.")
        return 0
    from backend.database import db  # noqa: E402
    with db.engine.begin() as conn:
        n = seed_case_milestones(conn, args.case_id, args.org_id, args.corridor_from,
                                 args.corridor_to, move, datetime.utcnow(), force=args.force)
    print(f"\nInserted {n} milestone(s)." if n else "\nNothing inserted (already seeded; use --force to replace).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
