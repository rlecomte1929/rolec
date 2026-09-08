#!/usr/bin/env python3
"""Verify the counsel-attestation Phase 1 migration landed correctly. READ-ONLY.

Run this AFTER applying 20261104000000_counsel_attestation_phase1.sql and before merging
the PR — the PR's readers assume these columns exist, and the column-read guard was waived
on exactly that promise.

    export DATABASE_URL='postgresql://...@aws-1-eu-west-1.pooler.supabase.com:5432/postgres'
    python scripts/verify_attestation_migration.py

Exit 0 = everything present and correctly secured. Exit 1 = something is missing; the
output names which check failed. Makes no writes of any kind.

Stdlib + psycopg2 only, so it runs without the app's import graph.
"""
import os
import sys

try:
    import psycopg2
except ImportError:  # pragma: no cover
    print("psycopg2 is required:  pip install psycopg2-binary")
    sys.exit(2)

TABLES = [
    "corridor_attestation_requests",
    "corridor_attestation_items",
    "corridor_attestation_signatures",
]
COLUMNS = ["attestation_status", "attested_at", "attested_by", "latest_attestation_request_id"]

CHECKS = []


def check(label, ok, detail=""):
    CHECKS.append((label, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  — ' + detail if detail else ''}")


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set.")
        return 2
    if ":6543" in url:
        print("Refusing to run against the transaction pooler (port 6543). Use session mode, port 5432.")
        return 2

    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        print("\nTables")
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name = ANY(%s)", (TABLES,))
        found = {r[0] for r in cur.fetchall()}
        for t in TABLES:
            check(f"public.{t} exists", t in found)

        print("\nrequirement_items columns")
        cur.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='requirement_items' AND column_name = ANY(%s)",
            (COLUMNS,))
        cols = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        for c in COLUMNS:
            check(f"requirement_items.{c} exists", c in cols,
                  f"{cols[c][0]}, nullable={cols[c][1]}" if c in cols else "")
        # Additive means every one of them must be nullable.
        for c, (_dtype, nullable) in cols.items():
            check(f"requirement_items.{c} is nullable (additive)", nullable == "YES")

        print("\nForeign key type match (the spec's uuid FK would have failed here)")
        cur.execute("""
            SELECT c.data_type FROM information_schema.columns c
            WHERE c.table_schema='public' AND c.table_name='corridor_attestation_items'
              AND c.column_name='requirement_item_id'""")
        row = cur.fetchone()
        check("corridor_attestation_items.requirement_item_id is character varying",
              bool(row) and row[0] == "character varying", row[0] if row else "missing")

        print("\nRLS")
        cur.execute(
            "SELECT tablename, rowsecurity FROM pg_tables "
            "WHERE schemaname='public' AND tablename = ANY(%s)", (TABLES,))
        rls = dict(cur.fetchall())
        for t in TABLES:
            check(f"{t} has RLS enabled", rls.get(t) is True)

        cur.execute(
            "SELECT tablename, count(*) FROM pg_policies "
            "WHERE schemaname='public' AND tablename = ANY(%s) GROUP BY 1", (TABLES,))
        pol = dict(cur.fetchall())
        for t in TABLES:
            check(f"{t} has >=1 policy (keeps rls_allowlist.txt at 0)", pol.get(t, 0) >= 1)

        print("\nNo anon / authenticated grants")
        cur.execute("""
            SELECT table_name, grantee, string_agg(privilege_type, ',') FROM information_schema.role_table_grants
            WHERE table_schema='public' AND table_name = ANY(%s)
              AND grantee IN ('anon','authenticated') GROUP BY 1,2""", (TABLES,))
        leaks = cur.fetchall()
        check("no anon/authenticated grants on the attestation tables", not leaks,
              "; ".join(f"{t}->{g}:{p}" for t, g, p in leaks) if leaks else "")

        print("\nLedger")
        cur.execute("SELECT version, name FROM supabase_migrations.schema_migrations "
                    "WHERE version = '20261104000000'")
        led = cur.fetchall()
        check("ledger records 20261104000000", len(led) == 1,
              str(led[0]) if led else "run: supabase migration repair --status applied 20261104000000")

        print("\nAdditive safety — no requirement_items row was rewritten")
        # Guarded: before the apply this column does not exist, and a traceback here would
        # bury the twelve useful FAIL lines above under a stack trace.
        if "attestation_status" in cols:
            cur.execute("SELECT count(*) FROM public.requirement_items WHERE attestation_status IS NOT NULL")
            n = cur.fetchone()[0]
            check("no row carries attestation_status yet (nothing machine-attested)", n == 0,
                  f"{n} row(s) already set" if n else "")
        else:
            check("no row carries attestation_status yet (nothing machine-attested)", False,
                  "skipped — the column does not exist yet, so the migration has not been applied")

    failed = [label for label, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed.")
    if failed:
        print("FAILED:\n  - " + "\n  - ".join(failed))
        return 1
    print("Migration verified. Safe to merge the PR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
