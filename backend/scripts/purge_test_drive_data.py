"""[AIQ-1545] Scoped, idempotent purge of test-drive data.

Read-time exclusion of synthetic rows already exists (``backend/db/test_data_filter.py``),
but there was no safe *deletion* path to reset between test-drive waves. This script provides
one: it deletes ONLY test-drive-owned data and proves the real (non-test) rows are untouched.

Scope (what it deletes):
  * ``test_sessions`` / ``survey_responses`` / ``funnel_events`` — these tables exist ONLY for
    the test-drive campaign; every row is test data, so they are purged in full.
  * ``feedback WHERE campaign IS NOT NULL`` — the campaign column is stamped ONLY by the
    test-drive flow (regular feedback has campaign NULL), so this targets test-drive feedback.
  * ``--include-tenants`` (opt-in): ``profiles`` / ``companies`` WHERE ``is_test = true`` — the
    durable synthetic-tenant marker. Left OFF by default because these are shared tables with
    real rows and FK dependents (cases/assignments) that carry no is_test marker; if a dependent
    FK blocks the delete the script reports it rather than force-cascading.

Safety:
  * DRY-RUN by default. Pass ``--execute`` to actually delete.
  * Idempotent — a second run deletes 0 rows.
  * Snapshots the real (non-test) counts before and after and ASSERTS they are unchanged.

Usage:
    python -m backend.scripts.purge_test_drive_data              # dry-run, report only
    python -m backend.scripts.purge_test_drive_data --execute    # delete test-drive tables
    python -m backend.scripts.purge_test_drive_data --execute --include-tenants
"""
from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Tuple

from sqlalchemy import text

from backend.app.db import engine

# (label, count-SQL, delete-SQL) — ordered children-before-parents for FK safety.
_TEST_DRIVE_TARGETS: List[Tuple[str, str, str]] = [
    ("survey_responses", "SELECT count(*) FROM survey_responses",
     "DELETE FROM survey_responses"),
    ("funnel_events", "SELECT count(*) FROM funnel_events",
     "DELETE FROM funnel_events"),
    ("test_sessions", "SELECT count(*) FROM test_sessions",
     "DELETE FROM test_sessions"),
    ("feedback (test-drive)", "SELECT count(*) FROM feedback WHERE campaign IS NOT NULL",
     "DELETE FROM feedback WHERE campaign IS NOT NULL"),
]

_TENANT_TARGETS: List[Tuple[str, str, str]] = [
    ("profiles (is_test)", "SELECT count(*) FROM profiles WHERE is_test = true",
     "DELETE FROM profiles WHERE is_test = true"),
    ("companies (is_test)", "SELECT count(*) FROM companies WHERE is_test = true",
     "DELETE FROM companies WHERE is_test = true"),
]

# Real-data invariants: these counts must be identical before and after the purge.
_REAL_INVARIANTS: Dict[str, str] = {
    "real companies": "SELECT count(*) FROM companies WHERE is_test = false",
    "real profiles": "SELECT count(*) FROM profiles WHERE is_test = false",
    "real feedback": "SELECT count(*) FROM feedback WHERE campaign IS NULL",
}


def _scalar(conn, sql: str) -> int:
    return int(conn.execute(text(sql)).scalar() or 0)


def _snapshot(conn, queries: Dict[str, str]) -> Dict[str, int]:
    return {label: _scalar(conn, sql) for label, sql in queries.items()}


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Purge test-drive data (dry-run by default).")
    ap.add_argument("--execute", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--include-tenants", action="store_true",
                    help="also purge is_test=true companies/profiles (may FK-block; opt-in)")
    args = ap.parse_args(argv)

    targets = list(_TEST_DRIVE_TARGETS)
    if args.include_tenants:
        targets += _TENANT_TARGETS

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"[purge_test_drive_data] mode={mode} include_tenants={args.include_tenants}\n")

    with engine.begin() as conn:
        real_before = _snapshot(conn, _REAL_INVARIANTS)

        deleted: Dict[str, int] = {}
        blocked: Dict[str, str] = {}
        for label, count_sql, delete_sql in targets:
            n = _scalar(conn, count_sql)
            if not args.execute:
                deleted[label] = n  # would-delete
                continue
            try:
                res = conn.execute(text(delete_sql))
                deleted[label] = int(getattr(res, "rowcount", 0) or 0)
            except Exception as exc:  # noqa: BLE001 — report FK/other blocks, don't abort the run
                blocked[label] = type(exc).__name__

        real_after = _snapshot(conn, _REAL_INVARIANTS)

        # Real-data invariant: a purge that touches a real row is a bug — roll back.
        drift = {k: (real_before[k], real_after[k]) for k in real_before if real_before[k] != real_after[k]}
        if args.execute and drift:
            print("ABORT — real-data counts changed, rolling back:")
            for k, (b, a) in drift.items():
                print(f"  {k}: {b} -> {a}")
            raise SystemExit(2)  # engine.begin() rolls back on exception

    verb = "deleted" if args.execute else "would delete"
    print(f"{'Target':<28} {verb}")
    print("-" * 42)
    for label, _c, _d in targets:
        print(f"{label:<28} {deleted.get(label, 0)}")
    if blocked:
        print("\nBLOCKED (left in place — likely FK dependents without an is_test marker):")
        for label, err in blocked.items():
            print(f"  {label}: {err}")
    print("\nReal-data invariants (unchanged):")
    for label, val in real_before.items():
        print(f"  {label}: {val}")
    if not args.execute:
        print("\nDry-run only — re-run with --execute to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
