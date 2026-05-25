#!/usr/bin/env python3
"""
RLS coverage check — AUDIT-A3 (audit/02-expert-security.md SEC-2).

Joins `pg_tables` × `pg_policies` against the live Supabase Postgres DB and
lists every table in the `public` schema with zero RLS policies. Compares the
result against `supabase/rls_allowlist.txt` (one tablename per line, comments
starting with `#`).

Exit codes:
  0 — all policy-less tables are on the allowlist (or there are none)
  1 — at least one policy-less table is NOT on the allowlist (CI should fail)
  2 — could not connect to DB or query failed (unexpected — investigate)

Usage:
  DATABASE_URL=postgresql://... python scripts/check_rls_coverage.py
  DATABASE_URL=postgresql://... python scripts/check_rls_coverage.py --json
  DATABASE_URL=postgresql://... python scripts/check_rls_coverage.py --update-allowlist

The --update-allowlist mode rewrites supabase/rls_allowlist.txt with the
current set of policy-less tables. Use this to seed the allowlist after
an initial review. Never wire --update-allowlist into CI.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_FILE = REPO_ROOT / "supabase" / "rls_allowlist.txt"

# Audit query: list every table in `public` schema with zero policies.
# pg_policies.tablename matches pg_tables.tablename for the same schema.
AUDIT_SQL = """
SELECT t.tablename
FROM pg_tables t
LEFT JOIN pg_policies p
       ON p.schemaname = t.schemaname
      AND p.tablename  = t.tablename
WHERE t.schemaname = 'public'
GROUP BY t.tablename
HAVING COUNT(p.policyname) = 0
ORDER BY t.tablename;
"""


def load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    allowed: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            allowed.add(line)
    return allowed


def query_policy_less_tables(db_url: str) -> list[str]:
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed — `pip install psycopg2-binary` or run from backend venv", file=sys.stderr)
        sys.exit(2)

    # Accept the Supabase pooler URL even if it starts with `postgres://` (legacy)
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:  # connection / DNS / auth
        print(f"could not connect to DATABASE_URL: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        with conn.cursor() as cur:
            cur.execute(AUDIT_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    return [r[0] for r in rows]


def write_allowlist(path: Path, tables: Iterable[str]) -> None:
    header = (
        "# supabase/rls_allowlist.txt\n"
        "# AUDIT-A3 — tables intentionally exposed without RLS policies.\n"
        "# Every entry MUST be reviewed by a human. Comment per entry with\n"
        "# the reason it is server-role-only (e.g. internal audit_log, ops\n"
        "# tables not exposed via the Supabase anon client, etc.).\n"
        "#\n"
        "# Format: one tablename per line. Lines starting with `#` are ignored.\n"
        "# Inline comments after a `#` on a name line are also ignored.\n"
        "#\n"
        "# This file is consulted by scripts/check_rls_coverage.py in CI.\n"
        "\n"
    )
    body = "\n".join(sorted(tables)) + ("\n" if tables else "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check RLS coverage against allowlist.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the diff as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--update-allowlist",
        action="store_true",
        help=(
            "Rewrite supabase/rls_allowlist.txt with the current set of "
            "policy-less tables. NEVER wire this into CI."
        ),
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    policy_less = query_policy_less_tables(db_url)
    allowlist = load_allowlist(ALLOWLIST_FILE)

    if args.update_allowlist:
        write_allowlist(ALLOWLIST_FILE, policy_less)
        print(f"[rls-coverage] wrote {len(policy_less)} entries to {ALLOWLIST_FILE.relative_to(REPO_ROOT)}")
        return 0

    missing = [t for t in policy_less if t not in allowlist]
    extra = sorted(allowlist - set(policy_less))  # in allowlist but now has a policy

    if args.json:
        print(json.dumps({
            "policy_less_total": len(policy_less),
            "allowlist_total": len(allowlist),
            "missing_from_allowlist": missing,
            "stale_allowlist_entries": extra,
            "pass": len(missing) == 0,
        }, indent=2))
    else:
        print(f"[rls-coverage] policy-less tables in public schema: {len(policy_less)}")
        print(f"[rls-coverage] allowlist entries: {len(allowlist)}")
        if missing:
            print(f"\n[rls-coverage] FAIL — {len(missing)} tables have no policy and are NOT on the allowlist:")
            for t in missing:
                print(f"  - {t}")
            print(
                "\nFix path:\n"
                "  1. Add a RLS policy in supabase/migrations/ for the table, OR\n"
                "  2. If the table is server-role-only and intentionally not exposed,\n"
                "     add it to supabase/rls_allowlist.txt with a comment explaining why.\n"
            )
        elif extra:
            print(f"\n[rls-coverage] WARN — {len(extra)} stale entries on allowlist now have policies:")
            for t in extra:
                print(f"  - {t}  (safe to remove from allowlist)")
        else:
            print("\n[rls-coverage] PASS — every policy-less table is on the allowlist.")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
