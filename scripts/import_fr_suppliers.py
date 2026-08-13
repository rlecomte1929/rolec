#!/usr/bin/env python3
"""
[AIQ-1827] Stage Paris supplier candidates for FR-NO from the French open company register.

Run from the repo root:

    # preview — queries the register, decides everything, writes nothing
    python scripts/import_fr_suppliers.py

    # stage into vendor_candidates
    python scripts/import_fr_suppliers.py --apply

    # ...and create the suppliers, each with ONE capability at platform_vetting_status='pending'
    python scripts/import_fr_suppliers.py --promote

Dry run is the DEFAULT and takes the same code path as a real run.

WHAT THESE ROWS CLAIM
---------------------
Tier 2: the company is REGISTERED in France and self-declared this activity. That is not a
bar membership, a carte T, or a place on the Ordre's tableau. Accreditations land
`status='claimed'` and cannot be auto-verified — `accreditation_hardening.BODY_POLICIES`
has no rule for this body, by design.

Nothing here becomes visible to an employee: every capability lands
`platform_vetting_status='pending'`, and `marketplace`/`test_drive` filter on `'approved'`.
Approval stays a human action at /admin/vetting-queue.

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
from backend.imports.suppliers.fr_sirene import NAF_BY_CATEGORY, harvest  # noqa: E402

CATEGORIES = tuple(NAF_BY_CATEGORY)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="actually stage into vendor_candidates (default: dry run)")
    ap.add_argument("--promote", action="store_true",
                    help="also create suppliers, each with one capability at "
                         "platform_vetting_status='pending'. Implies --apply.")
    ap.add_argument("--per-category", type=int, default=5,
                    help="how many candidates to keep per category (default 5)")
    ap.add_argument("--category", action="append", choices=CATEGORIES,
                    help="restrict to one category (repeatable; default: all four)")
    args = ap.parse_args()
    if args.promote:
        args.apply = True

    categories = tuple(args.category) if args.category else CATEGORIES

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set — even a dry run reads suppliers + "
              "vendor_candidates to decide what is a duplicate")
        return 2

    print(f"querying INSEE SIRENE for {len(categories)} categor(y/ies) across Paris…\n")
    by_category = harvest(categories, per_category=args.per_category)

    for cat in categories:
        got = by_category.get(cat, [])
        print(f"  {cat:18} {len(got)} candidate(s)")
        for c in got:
            print(f"      - {c.name[:58]:60} SIREN {c.accreditation_number}")
    print()

    candidates = [c for cat in categories for c in by_category.get(cat, [])]
    if not candidates:
        print("✖ no candidates — the register returned nothing for any category.")
        print("  That is a finding, not an empty run: re-check the NAF codes and the API.")
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
        # No promote preview here, deliberately. Nothing has been staged, so promote() would
        # report the PRE-EXISTING backlog rather than this harvest — 235 suppliers on
        # 2026-08-13, of which 233 are corridor-NULL rows from an older import. Printing that
        # next to a 16-row harvest reads as "this run creates 235 suppliers", which is false.
        print()
        print(f"promote:    would create {len(candidates)} supplier(s) from THIS harvest, "
              f"each with one capability at platform_vetting_status='pending'")
        print("  (preview — run --apply to stage, then --promote to create them)")
    elif args.promote:
        from sqlalchemy.orm import sessionmaker

        with sessionmaker(bind=engine)() as session:
            # Scoped to this run. Unscoped promotion would sweep every abandoned candidate
            # in the table along with ours.
            n, skipped, problems = promote(session, dry_run=False, run_ids=run_ids)
            print()
            print(f"promote:    {n} supplier(s) -> vetting queue "
                  f"(platform_vetting_status='pending')")
            if skipped:
                print(f"  skipped:  {skipped}")
                for p_ in problems[:10]:
                    print(f"    - {p_}")

    if rejections:
        print(f"\n⚠ {len(rejections)} row(s) rejected — nothing about them was staged.")
        print("  The reject list is the re-sourcing worklist, not noise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
