#!/usr/bin/env python3
"""
RLS coverage check — AUDIT-A3 (audit/02-expert-security.md SEC-2).

Joins `pg_tables` × `pg_policies` against the live Supabase Postgres DB and
lists every table in the audited schemas (`public` and `rce`) with zero RLS
policies. Compares the result against `supabase/rls_allowlist.txt` (one name per
line, comments starting with `#`). `public` tables are listed bare; non-public
schemas are qualified as `schema.table` (e.g. `rce.foo`), so an rce allowlist
entry would read `rce.foo`. `rce` needs 0 entries today (29/29 tables covered).

Exit codes:
  0 — all policy-less tables are on the allowlist (or there are none), and every
      allowlisted table is still unreachable through PostgREST
  1 — a policy-less table is NOT on the allowlist; OR an allowlisted table has since
      been granted to `anon`/`authenticated`, retiring its justification; OR the audit
      examined 0 tables (CI should fail in all three cases)
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

# Schemas audited for RLS coverage. `public` is exposed via PostgREST + the anon
# key; `rce` is service-role-only today but a future policy-less rce table should
# still fail CI (SEC-RLSh / AIQ-950).
AUDITED_SCHEMAS = ("public", "rce")

# Audit query: list every (schema, table) in the audited schemas with zero
# policies. pg_policies.(schemaname, tablename) matches pg_tables for the same row.
AUDIT_SQL = """
SELECT t.schemaname, t.tablename
FROM pg_tables t
LEFT JOIN pg_policies p
       ON p.schemaname = t.schemaname
      AND p.tablename  = t.tablename
WHERE t.schemaname = ANY(%s)
GROUP BY t.schemaname, t.tablename
HAVING COUNT(p.policyname) = 0
ORDER BY t.schemaname, t.tablename;
"""

# Every allowlist entry is justified by the same claim: "server-role-only, not reachable
# through the Supabase anon client". That claim is checkable, and it can expire without
# anyone noticing — a later GRANT, or a Supabase default applied to a new table, exposes a
# policy-less table while the allowlist keeps the guard quiet forever.
#
# So the allowlist is verified rather than trusted: an entry that has picked up a grant to
# `anon` or `authenticated` fails. This is the difference between an exception with a
# reason and a blindfold, and it is why "add it to the allowlist" is safe advice here at
# all. PostgREST reaches the public schema through exactly these two roles.
GRANTS_SQL = """
SELECT g.table_schema, g.table_name, g.grantee,
       string_agg(DISTINCT g.privilege_type, ',' ORDER BY g.privilege_type)
FROM information_schema.role_table_grants g
WHERE g.table_schema = ANY(%s)
  AND g.grantee IN ('anon', 'authenticated')
GROUP BY g.table_schema, g.table_name, g.grantee
ORDER BY g.table_schema, g.table_name, g.grantee;
"""

# How many tables the audit looked at AT ALL. `AUDIT_SQL` returns only the offenders, so
# "0 policy-less tables" is the same output whether every table is covered or the query
# matched nothing — a renamed schema, a `pg_tables` permission change on the read-only
# role, an empty database. This guard's whole job is to be believed when it is green, so
# it has to be able to say what it examined. Same reason check_compliance_claims.py fails
# on `scanned == 0` and check_route_auth.py fails on `examined == 0`.
TABLE_COUNT_SQL = """
SELECT count(*) FROM pg_tables WHERE schemaname = ANY(%s);
"""


def qualify_table(schemaname: str, tablename: str) -> str:
    """Display/allowlist name for a policy-less table. `public` tables stay BARE
    so the existing public allowlist and its behaviour are unchanged; non-public
    schemas are qualified as ``schema.table`` (e.g. ``rce.foo``)."""
    return tablename if schemaname == "public" else f"{schemaname}.{tablename}"


def load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    allowed: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            allowed.add(line)
    return allowed


def missing_from_allowlist(
    policy_less: Iterable[str], allowlist: "set[str]"
) -> "list[str]":
    """Policy-less tables that are NOT on the allowlist — i.e. the ones that must
    FAIL the gate. Pure function (no DB) so the fail path is unit-testable: a new
    public table with no RLS policy and no allowlist entry lands here → exit 1.
    """
    return [t for t in policy_less if t not in allowlist]


def find_unjustified_allowlist_entries(path: Path) -> "list[tuple[int, str]]":
    """Return ``(line_no, tablename)`` for every allowlist entry lacking a
    justification comment (SEC-RLSf / AIQ-663).

    An entry is justified if it carries EITHER:
      - an inline reason — ``tablename  # why it's server-role-only``, OR
      - a ``#`` comment / section header directly above it. A header opens a
        section that covers every entry beneath it until a blank line resets it.

    Static check — no DB required, so it runs even when the RLS-coverage DB
    secret is absent. A bare ``tablename`` with no reason is a failure.
    """
    if not path.exists():
        return []
    offenders: "list[tuple[int, str]]" = []
    in_section = False  # under a comment / section header
    for i, raw in enumerate(path.read_text().splitlines()):
        stripped = raw.strip()
        if not stripped:
            in_section = False  # blank line ends the current section
            continue
        if stripped.startswith("#"):
            in_section = True
            continue
        name, _, comment = raw.partition("#")
        name = name.strip()
        if name and not comment.strip() and not in_section:
            offenders.append((i + 1, name))
    return offenders


def query_policy_less_tables(
    db_url: str,
) -> "tuple[list[str], dict[str, list[str]], int]":
    """Return ``(policy_less, exposed_grants, tables_examined)``.

    ``exposed_grants`` maps a table name to the ``anon``/``authenticated`` grants it
    carries, so an allowlist entry's "server-role-only" justification can be re-verified
    instead of taken on trust. ``tables_examined`` is every table in the audited schemas,
    so a green result can state its own coverage.
    """
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
            cur.execute(AUDIT_SQL, (list(AUDITED_SCHEMAS),))
            rows = cur.fetchall()
            cur.execute(GRANTS_SQL, (list(AUDITED_SCHEMAS),))
            grant_rows = cur.fetchall()
            cur.execute(TABLE_COUNT_SQL, (list(AUDITED_SCHEMAS),))
            tables_examined = cur.fetchone()[0]
    finally:
        conn.close()

    exposed: dict[str, list[str]] = {}
    for schemaname, tablename, grantee, privs in grant_rows:
        exposed.setdefault(qualify_table(schemaname, tablename), []).append(
            f"{grantee}:{privs}"
        )

    return (
        [qualify_table(schemaname, tablename) for schemaname, tablename in rows],
        exposed,
        int(tables_examined),
    )


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

    # SEC-RLSf (AIQ-663): static guard — every retained allowlist entry must
    # carry a justification. Runs first, with no DB dependency, so an
    # unjustified entry fails CI even where the RLS-coverage DB secret is unset.
    # Skipped for --update-allowlist, which (re)seeds the file.
    if not args.update_allowlist:
        unjustified = find_unjustified_allowlist_entries(ALLOWLIST_FILE)
        if unjustified:
            print(
                f"[rls-coverage] FAIL — {len(unjustified)} allowlist entr"
                f"{'y' if len(unjustified) == 1 else 'ies'} without a justification comment:",
                file=sys.stderr,
            )
            for line_no, name in unjustified:
                print(f"  {ALLOWLIST_FILE.name}:{line_no}: {name}", file=sys.stderr)
            print(
                "  Add an inline `# reason` after the name, or a `#` section header "
                "above the block, explaining why the table is server-role-only.",
                file=sys.stderr,
            )
            return 1

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    policy_less, exposed_grants, tables_examined = query_policy_less_tables(db_url)
    allowlist = load_allowlist(ALLOWLIST_FILE)

    # Nothing below means anything if the audit saw no tables. Checked before the
    # --update-allowlist branch too: seeding an allowlist from an empty result would
    # write an empty file and call it a drained allowlist.
    if tables_examined == 0:
        print(
            "[rls-coverage] FAIL — examined 0 tables in "
            f"{'+'.join(AUDITED_SCHEMAS)}.",
            file=sys.stderr,
        )
        print(
            "  The audit query matched nothing, so 'no policy-less tables' is not a\n"
            "  pass — it is a broken query. Check the schema names, and that the\n"
            "  DATABASE_URL role can read pg_tables.",
            file=sys.stderr,
        )
        return 1

    if args.update_allowlist:
        write_allowlist(ALLOWLIST_FILE, policy_less)
        print(f"[rls-coverage] wrote {len(policy_less)} entries to {ALLOWLIST_FILE.relative_to(REPO_ROOT)}")
        return 0

    missing = missing_from_allowlist(policy_less, allowlist)
    extra = sorted(allowlist - set(policy_less))  # in allowlist but now has a policy

    # An allowlisted table is excused because it is server-role-only. Confirm that is
    # still true: a later GRANT to anon/authenticated exposes a policy-less table while
    # the allowlist keeps this guard silent. Verified, not trusted.
    expired = sorted(
        (t, exposed_grants[t]) for t in allowlist if t in exposed_grants
    )

    if args.json:
        print(json.dumps({
            "tables_examined": tables_examined,
            "policy_less_total": len(policy_less),
            "allowlist_total": len(allowlist),
            "missing_from_allowlist": missing,
            "stale_allowlist_entries": extra,
            # Every allowlisted table that has since picked up a PostgREST-reachable
            # grant. Reported here as well as in the text output, and counted in `pass`
            # — a JSON consumer reading `pass: true` while the process exits 1 is its
            # own silent-pass bug.
            "expired_justifications": [
                {"table": t, "grants": grants} for t, grants in expired
            ],
            "pass": not missing and not expired,
        }, indent=2))
    else:
        print(f"[rls-coverage] tables examined in {'+'.join(AUDITED_SCHEMAS)} schemas: {tables_examined}")
        print(f"[rls-coverage] policy-less tables: {len(policy_less)}")
        print(f"[rls-coverage] allowlist entries: {len(allowlist)} (grants re-verified)")
        if expired:
            print(
                f"\n[rls-coverage] FAIL — {len(expired)} allowlisted table(s) are now "
                "reachable through PostgREST:"
            )
            for t, grants in expired:
                print(f"  - {t}  ({'; '.join(grants)})")
            print(
                "\nThese are excused from needing a policy because they are server-role-only.\n"
                "A grant to anon/authenticated retires that justification: the table is\n"
                "policy-less AND reachable. Revoke the grant, or add a real RLS policy and\n"
                "drop the allowlist entry."
            )
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
            print(
                f"\n[rls-coverage] PASS — {tables_examined} tables examined; every "
                "policy-less table is allowlisted and still server-role-only."
            )

    return 1 if (missing or expired) else 0


if __name__ == "__main__":
    sys.exit(main())
