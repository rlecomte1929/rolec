#!/usr/bin/env python3
"""Stage a vendor-candidate CSV, then SCOPED-promote only what this run staged.

Why this exists alongside `import_supplier_candidates.py`: that script's `--promote` calls
`executor.promote(session)` with no `run_ids`, which promotes EVERY unpromoted candidate in
the table — including rows an earlier import staged and abandoned (measured 2026-08-13: 233
corridor-NULL rows made a 16-row French harvest preview as "promote: 235 suppliers"). That is
the unscoped-promote foot-gun. This wrapper captures the `run_id`s that `stage()` opens in THIS
invocation and passes them to `executor.promote(session, run_ids=[...])`, so promotion can never
reach beyond the rows you just staged.

Everything else is unchanged and still gated:
  * `stage()` writes only `vendor_curation_runs` + `vendor_candidates` (status='pending').
  * `promote()` creates `suppliers` + one `supplier_service_capabilities` row at
    `platform_vetting_status='pending'` -> visible ONLY in /admin/vetting-queue. Nothing
    reaches an employee: marketplace and test_drive both filter on 'approved'.
  * Rejected rows are never staged; they are written to a worklist instead of aborting, since
    a registry harvest legitimately rejects the majority (the rejects ARE the re-sourcing list).

Usage (dry run is the default and takes the same code path a real run would):

    python scripts/land_vendor_candidates.py <csv>                       # preview
    python scripts/land_vendor_candidates.py <csv> --apply               # stage only
    python scripts/land_vendor_candidates.py <csv> --apply --promote     # stage + scoped promote
    python scripts/land_vendor_candidates.py <csv> --worklist rejects.md  # save the reject list

Reads DATABASE_URL. Even a dry run reads suppliers + vendor_candidates to decide duplicates.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.suppliers.executor import promote, stage, summarise  # noqa: E402
from backend.imports.suppliers.parsers import RowError, read_csv  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="harvest CSV (see EXPECTED_HEADER in parsers.py)")
    ap.add_argument("--apply", action="store_true", help="actually stage (default: dry run)")
    ap.add_argument(
        "--promote", action="store_true",
        help="after staging, create suppliers for ONLY this run's candidates, each with one "
             "capability at platform_vetting_status='pending' (=> /admin/vetting-queue). "
             "Implies --apply.",
    )
    ap.add_argument("--worklist", type=Path, help="write the rejected rows here (re-sourcing list)")
    args = ap.parse_args()
    if args.promote:
        args.apply = True

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
        print("✖ DATABASE_URL is not set — even a dry run reads suppliers + vendor_candidates")
        return 2

    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True)
    print(f"mode: {'APPLY' if args.apply else 'DRY RUN — nothing will be written'}\n")

    run_ids = []
    with engine.begin() as conn:
        results, rejections = stage(conn, candidates, dry_run=not args.apply)
        print(summarise(results, rejections))
        run_ids = [r.run_id for r in results if r.run_id]
        if not args.apply:
            conn.rollback()

    if args.worklist and rejections:
        args.worklist.write_text(
            "# Vendor re-sourcing worklist\n\n"
            f"{len(rejections)} row(s) rejected by the tier gate — re-source each against a real "
            "register (cite the register's per-entity URL, not the provider's own site), then "
            "re-run this importer.\n\n"
            + "\n".join(f"- {r}" for r in rejections) + "\n",
            encoding="utf-8",
        )
        print(f"\nworklist: {len(rejections)} rejected row(s) -> {args.worklist}")

    # SCOPED promote: only the runs THIS invocation opened. run_ids exist solely after
    # --apply; a later "promote" call would create no new runs (staging is idempotent), so
    # promotion must happen in the same invocation that staged — pass --apply --promote.
    if not args.apply:
        print("\n(dry run — re-run with --apply to stage; add --promote to scoped-promote "
              "the newly-staged rows into the /admin/vetting-queue in the same run)")
        return 0

    from sqlalchemy.orm import sessionmaker

    with sessionmaker(bind=engine)() as session:
        # dry_run=True still previews accurately here because run_ids now name real runs.
        n, skipped, problems = promote(session, dry_run=not args.promote, run_ids=run_ids)
        print()
        print(f"promote:    {n} supplier(s) -> vetting queue (platform_vetting_status='pending')"
              f"   [scoped to {len(run_ids)} run(s) staged here]")
        if skipped:
            print(f"  skipped:  {skipped}")
        for p_ in problems:
            print(f"    - {p_}")
        if not args.promote:
            print("  (preview — add --promote to write these suppliers)")
            session.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
