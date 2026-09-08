#!/usr/bin/env python3
"""
[Stage 9 · Phase 0] Stage FIDI affiliates for a country as origin-side mover supply.

Run from the repo root:

    # preview — queries the FIDI directory, decides everything, writes nothing
    python scripts/import_fidi_suppliers.py

    # stage into vendor_candidates
    python scripts/import_fidi_suppliers.py --apply

    # ...and create the suppliers, each with ONE capability at platform_vetting_status='pending'
    python scripts/import_fidi_suppliers.py --promote

Dry run is the DEFAULT and takes the same code path as a real run.

WHY THIS EXISTS
---------------
Phase 0 needed "≥3 FR-based movers with evidenced Norway reach" and production had zero. The
French movers in the directory came from INSEE SIRENE and are tier 2 — a SIREN plus NAF 49.42Z
proves a company is registered, not that it can move a household to Oslo.

FIDI is tier 1 and turned out to be enumerable: `/find-fidi-affiliate?country=101` lists 11
French affiliates, each with a per-entity detail page carrying a FAIM certificate expiry.

WHAT THESE ROWS CLAIM
---------------------
Accreditations land `status='claimed'`, like every harvest. FIDI membership becomes `verified`
only when `scripts/harden_accreditations.py` fetches the affiliate page and finds the entity
name — a separate, evidenced step. Only then does §S2 `vendor_reaches()` rule 3 hold.

Nothing here becomes visible to an employee: capabilities land
`platform_vetting_status='pending'`, and `marketplace`/`test_drive` filter on `'approved'`.
Approval stays a human decision at /admin/vetting-queue.

Reads DATABASE_URL.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.suppliers.executor import promote, stage, summarise  # noqa: E402
from backend.imports.suppliers.fidi_directory import COUNTRY_IDS, harvest  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country", default="FR", choices=sorted(COUNTRY_IDS),
                    help="FIDI country to harvest (default FR)")
    ap.add_argument("--apply", action="store_true",
                    help="actually stage into vendor_candidates (default: dry run)")
    ap.add_argument("--promote", action="store_true",
                    help="also create suppliers, each with one capability at "
                         "platform_vetting_status='pending'. Implies --apply.")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap the number of affiliates (default: all the country lists)")
    args = ap.parse_args()
    if args.promote:
        args.apply = True

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set — even a dry run reads suppliers + "
              "vendor_candidates to decide what is a duplicate")
        return 2

    print(f"querying the FIDI affiliate directory for {args.country}…\n")
    candidates, problems = harvest(args.country, limit=args.limit)

    for c in candidates:
        plus = "Plus" if "Plus" in (c.accreditation_body or "") else "    "
        expiry = c.accreditation_expiry or "no expiry published"
        print(f"  {c.name[:46]:48} FAIM {plus}  valid through {expiry}")
    print()

    if problems:
        print(f"⚠ {len(problems)} problem(s) — reported, not swallowed:")
        for p_ in problems:
            print(f"    - {p_}")
        print()

    if not candidates:
        print("✖ no affiliates harvested. That is a finding, not an empty run:")
        print("  re-check the country id in fidi_directory.COUNTRY_IDS and the index URL.")
        return 1

    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True)
    mode = "APPLY" if args.apply else "DRY RUN — nothing will be written"
    print(f"mode: {mode}\n")

    with engine.begin() as conn:
        results, rejections = stage(conn, candidates, dry_run=not args.apply)
        print(summarise(results, rejections))
        if not args.apply:
            conn.rollback()

    run_ids = [r.run_id for r in results if getattr(r, "run_id", None)]

    if not args.apply:
        # No promote preview. Nothing is staged yet, so promote() would report the
        # PRE-EXISTING backlog — 233 unpromoted corridor-NULL rows from an older import —
        # rather than this harvest, which reads as "this run creates 235 suppliers".
        print()
        print(f"promote:    would create up to {len(candidates)} supplier(s) from THIS harvest, "
              f"each with one capability at platform_vetting_status='pending'")
        print("  (preview — run --apply to stage, then --promote to create them)")
    elif args.promote:
        from sqlalchemy.orm import sessionmaker

        with sessionmaker(bind=engine)() as session:
            # Scoped to this run. Unscoped promotion sweeps every abandoned candidate.
            n, skipped, problems_ = promote(session, dry_run=False, run_ids=run_ids)
            print()
            print(f"promote:    {n} supplier(s) -> vetting queue "
                  f"(platform_vetting_status='pending')")
            if skipped:
                print(f"  skipped:  {skipped}")
                for p_ in problems_[:10]:
                    print(f"    - {p_}")

    if rejections:
        print(f"\n⚠ {len(rejections)} row(s) rejected — nothing about them was staged.")
        print("  The reject list is the re-sourcing worklist, not noise.")

    print("\nNext: run scripts/harden_accreditations.py --apply to confirm the FIDI")
    print("accreditations against their own affiliate pages. Approval of")
    print("platform_vetting_status remains a human decision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
