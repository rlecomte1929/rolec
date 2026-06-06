#!/usr/bin/env python3
"""
Migration-ledger drift check — AIQ-756-PREVENT.

Compares the migration versions APPLIED on the live/staging Supabase
(`supabase_migrations.schema_migrations.version`) against the version prefixes
of the repo's `supabase/migrations/*.sql` files, and fails when prod has an
applied version with **no matching repo file**.

That mismatch is what makes a fresh `supabase db push` / Supabase Preview abort
with `Remote migration versions not found in local migrations directory`, turning
EVERY PR's Preview red until someone reconciles by hand (see AIQ-756). It happens
because `MCP apply_migration` records an apply-TIME version (e.g. 20260604140233)
while the committed file carries a forward timestamp (e.g. 20260608100000). This
guard catches that drift at PR time instead of after merge.

Direction matters — only the **prod-not-in-repo** direction is an error:
  * prod version with no repo file  -> DRIFT (fail): `db push` can't find it.
  * repo version not yet on prod     -> fine: undeployed work; Preview replays it.

Exit codes (mirrors scripts/check_rls_coverage.py):
  0 — every applied prod version has a matching repo file (or none drift)
  1 — at least one prod version has no repo file (CI should fail)
  2 — could not connect to DB / query failed (unexpected — investigate)

Usage:
  DATABASE_URL=postgresql://... python scripts/check_migration_drift.py
  DATABASE_URL=postgresql://... python scripts/check_migration_drift.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

# A migration filename is "<14-digit-version>_<name>.sql".
_FILENAME_RE = re.compile(r"^(\d{14})_(.+)\.sql$")

_APPLIED_SQL = "SELECT version, name FROM supabase_migrations.schema_migrations;"


# ---------------------------------------------------------------------------
# Pure logic (unit-tested without a DB)
# ---------------------------------------------------------------------------

def repo_versions(migrations_dir: Path) -> Set[str]:
    """Set of 14-digit version prefixes of every supabase/migrations/*.sql file."""
    out: Set[str] = set()
    if not migrations_dir.exists():
        return out
    for p in migrations_dir.glob("*.sql"):
        m = _FILENAME_RE.match(p.name)
        if m:
            out.add(m.group(1))
    return out


def repo_versions_by_name(migrations_dir: Path) -> Dict[str, str]:
    """Map migration name -> its repo version, to suggest a reconciliation target."""
    out: Dict[str, str] = {}
    if not migrations_dir.exists():
        return out
    for p in migrations_dir.glob("*.sql"):
        m = _FILENAME_RE.match(p.name)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def repo_files_by_version(migrations_dir: Path) -> Dict[str, str]:
    """Map repo version -> migration name, for the Direction-B (repo-not-on-prod) check."""
    out: Dict[str, str] = {}
    if not migrations_dir.exists():
        return out
    for p in migrations_dir.glob("*.sql"):
        m = _FILENAME_RE.match(p.name)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def find_drift(applied: Dict[str, str], repo_vers: Set[str]) -> List[Dict[str, str]]:
    """
    Return the prod-applied (version, name) rows whose version has no repo file.

    `applied` maps prod version -> migration name. Sorted by version for stable output.
    """
    drift = [
        {"version": ver, "name": name}
        for ver, name in applied.items()
        if ver not in repo_vers
    ]
    return sorted(drift, key=lambda d: d["version"])


def find_repo_only(applied: Dict[str, str], repo_by_version: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Direction B (warning): repo migration files whose version has no prod row.

    `applied` maps prod version -> name; `repo_by_version` maps repo version -> name.
    This is legitimate for undeployed work on a PR branch, but it makes
    `db push` / Supabase Branching fail with 'local migration files not found in
    remote database' — so it's surfaced as a WARNING, not a hard failure.
    """
    repo_only = [
        {"version": ver, "name": name}
        for ver, name in repo_by_version.items()
        if ver not in applied
    ]
    return sorted(repo_only, key=lambda d: d["version"])


# ---------------------------------------------------------------------------
# DB access (mirrors check_rls_coverage.py)
# ---------------------------------------------------------------------------

def query_applied_versions(db_url: str) -> Dict[str, str]:
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed — `pip install psycopg2-binary` or run from backend venv", file=sys.stderr)
        sys.exit(2)

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:
        print(f"could not connect to DATABASE_URL: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        with conn.cursor() as cur:
            cur.execute(_APPLIED_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    return {r[0]: (r[1] or "") for r in rows}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Check prod migration ledger vs repo files.")
    parser.add_argument("--json", action="store_true", help="Output drift as JSON.")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    applied = query_applied_versions(db_url)
    repo_vers = repo_versions(MIGRATIONS_DIR)
    repo_by_ver = repo_files_by_version(MIGRATIONS_DIR)
    by_name = repo_versions_by_name(MIGRATIONS_DIR)
    drift = find_drift(applied, repo_vers)          # Direction A — prod not in repo (hard fail)
    repo_only = find_repo_only(applied, repo_by_ver)  # Direction B — repo not on prod (warning)

    # Annotate each drift row with a suggested reconciliation target if the same
    # migration NAME exists in the repo at a different version (the common case:
    # apply-time version vs committed forward-timestamp version).
    for d in drift:
        repo_ver = by_name.get(d["name"])
        d["suggested_repo_version"] = repo_ver if repo_ver and repo_ver != d["version"] else None

    if args.json:
        print(json.dumps(
            {"drift": drift, "count": len(drift),
             "repo_only": repo_only, "warn_count": len(repo_only)},
            indent=2,
        ))

    # Direction A — prod version with no repo file. This is the ONLY hard failure.
    if drift and not args.json:
        print(f"❌  Migration-drift check FAILED — {len(drift)} prod version(s) have NO repo file:")
        print("    (this is what makes `db push` / Supabase Preview fail with")
        print("     'Remote migration versions not found in local migrations directory')\n")
        for d in drift:
            if d["suggested_repo_version"]:
                print(f"  • {d['version']}  {d['name']}")
                print(f"      → repo has this migration at {d['suggested_repo_version']}. Reconcile the ledger:")
                print(f"        UPDATE supabase_migrations.schema_migrations SET version='{d['suggested_repo_version']}'")
                print(f"          WHERE version='{d['version']}' AND name='{d['name']}';  -- collision-check first")
            else:
                print(f"  • {d['version']}  {d['name']}  → no repo file by this name; commit a prod-as-oracle "
                      f"migration at version {d['version']} (real DDL or stub).")
        print("\n  Prevention: don't pre-apply repo-tracked migrations via MCP apply_migration — commit the")
        print("  file and let the main-push migration workflow apply it (it records the repo version). See CLAUDE.md.")

    # Direction B — repo file with no prod row. WARNING only (exit 0): legitimate for
    # undeployed work on a PR branch, but it breaks `db push` / Supabase Branching.
    if repo_only and not args.json:
        print(f"\n⚠  WARN — {len(repo_only)} repo migration file(s) have no matching prod row:")
        for r in repo_only:
            print(f"  • {r['version']}_{r['name']}.sql has no matching prod row.")
        print("     Apply the migration or delete the file if it was committed by mistake.")
        print("     This will cause `db push` / Supabase Branching to fail with")
        print("     'local migration files not found in remote database'.")

    # Summary line — always printed.
    if not args.json:
        mark = "❌" if drift else ("⚠ " if repo_only else "✅")
        print(f"{mark}  Migration ledger: {len(applied)} prod rows, {len(repo_by_ver)} repo files, "
              f"{len(drift)} mismatch(es), {len(repo_only)} repo-ahead warning(s).")

    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
