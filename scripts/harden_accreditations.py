#!/usr/bin/env python3
"""
[AIQ-1826] Move FR-NO supplier accreditations from `claimed` to `verified` — but only the
ones a live register actually confirms.

Run from the repo root:

    # preview — reads rows, fetches every register page, decides everything, writes nothing
    python scripts/harden_accreditations.py

    # write
    python scripts/harden_accreditations.py --apply

Dry run is the DEFAULT and takes the same code path as a real run, so its counts are the
counts you will get.

WHAT THIS WILL AND WILL NOT DO
------------------------------
It UPDATEs `supplier_accreditations` only. It creates nothing, deletes nothing, and does not
touch `supplier_service_capabilities` — so it cannot change what any employee sees. The
recommendation path filters on `platform_vetting_status='approved'`, a separate human gate.

A row becomes `verified` on exactly one condition: its own `evidence_url` was fetched and the
page names the entity. A register that is unreachable leaves the row `claimed` (we failed to
check — that is not a finding about the supplier). A register that answers without naming the
entity marks the row `not_found`, which is a real finding and deliberately louder than
`claimed`.

Scope is the FR-NO corridor and four categories. The other rows in the table — the German
FR-DE ones, including a bank — are reported as skipped and never written.

Reads DATABASE_URL.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.accreditation_hardening import render_report  # noqa: E402
from backend.imports.suppliers.harden import apply, load_rows, plan  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default: dry run)")
    ap.add_argument("--no-notes", action="store_true",
                    help="do not write the reason onto rows that stay 'claimed' "
                         "(status changes are unaffected)")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set — even a dry run reads the accreditation rows")
        return 2

    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True)

    with engine.connect() as conn:
        rows = load_rows(conn)
    print(f"read {len(rows)} accreditation(s)\n")

    # Fetching happens outside any transaction: register lookups are slow and must not hold
    # a write lock open across the network.
    decisions = plan(rows)
    print(render_report(decisions, dry_run=not args.apply))

    with engine.begin() as conn:
        verified, annotated = apply(
            conn, decisions,
            dry_run=not args.apply,
            record_reasons=not args.no_notes,
        )

    print()
    verb = "written" if args.apply else "would write"
    print(f"{verb}: {verified} status -> verified, "
          f"{annotated} note-only (status unchanged)")
    if not args.apply:
        print("  (preview — pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
