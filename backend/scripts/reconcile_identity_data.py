#!/usr/bin/env python3
"""
Audit and optionally repair identity / employee-contact / assignment consistency.

Usage (from repo root):
  PYTHONPATH=. python backend/scripts/reconcile_identity_data.py
  PYTHONPATH=. python backend/scripts/reconcile_identity_data.py --apply
  PYTHONPATH=. python backend/scripts/reconcile_identity_data.py --json-out /tmp/identity-audit.json

Uses DATABASE_URL from the environment (see backend/db_config.py). Default is dry-run only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
os.chdir(_REPO_ROOT)

# Avoid demo reseed side effects when DATABASE_URL points at local SQLite file
os.environ.setdefault("DISABLE_DEMO_RESEED", "true")

from backend.database import Database  # noqa: E402
from backend.services.identity_data_reconciliation import apply_safe_fixes, audit_identity_data  # noqa: E402


def _print_counts(title: str, counts: dict) -> None:
    print(f"\n{title}")
    print("-" * 60)
    for k in sorted(counts.keys()):
        print(f"  {k}: {counts[k]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Identity / assignment data reconciliation audit & safe fixes")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply auto-fixes (default: dry-run — audit + simulated fixes rolled back)",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default="",
        help="Write full JSON report (counts, manual samples, auto-fixes, errors) to this path",
    )
    parser.add_argument(
        "--limit-manual-print",
        type=int,
        default=20,
        help="Max manual-review rows to print to stdout (full list still in JSON if --json-out)",
    )
    args = parser.parse_args()

    db = Database()
    report = audit_identity_data(db.engine)
    _print_counts("Issue counts (audit)", report.counts)

    dry_run = not args.apply
    applied = apply_safe_fixes(db.engine, report, dry_run=dry_run)
    _print_counts("Auto-fix actions " + ("(dry-run, rolled back)" if dry_run else "(committed)"), applied)

    if report.errors:
        print("\nErrors / skipped queries:")
        for e in report.errors:
            print(f"  - {e}")

    lim = max(0, args.limit_manual_print)
    if report.manual_review and lim:
        print(f"\nManual review (first {lim} rows):")
        for row in report.manual_review[:lim]:
            print(f"  {json.dumps(row, default=str)}")

    payload = {
        "dryRun": dry_run,
        "counts": report.counts,
        "applied": applied,
        "manualReview": report.manual_review,
        "autoFixes": report.auto_fixes,
        "errors": report.errors,
    }
    if args.json_out:
        path = os.path.abspath(args.json_out)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\nWrote JSON report to {path}")

    if dry_run and any(applied.values()):
        print("\nNote: Dry-run executed fixes in a rolled-back transaction; database unchanged.")
        print("Re-run with --apply to persist safe fixes after reviewing this output.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
