#!/usr/bin/env python3
"""
Purge E2E test data — everything tagged `is_test = true`.

Pre-launch there are no real customers, but we still scope strictly to the
durable `is_test` flag (set automatically for @testco.com / @probe.test on
companies + profiles). That predicate deliberately does NOT match the
@testcompany.com / @*-demo.com demo tenants, so a purge can never touch demo
or real data.

SAFE BY DEFAULT: runs in --dry-run mode (counts only). Pass --apply to delete.
Deletes children before parents (no FK CASCADE in this schema), inside one
transaction, then verifies the is_test counts are 0.

Usage:
    DATABASE_URL=postgres://... python3 scripts/e2e_purge.py            # dry-run
    DATABASE_URL=postgres://... python3 scripts/e2e_purge.py --apply    # delete
"""
import argparse
import os
import sys

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 not installed — `pip install psycopg2-binary`")

# Case child tables in FK-safe delete order (scoped to test cases). Each entry is
# (table, key_column, id_source) where id_source is 'case' or 'assignment'.
CASE_CHILDREN = [
    ("wizard_employee_profiles", "assignment_id", "assignment"),
    ("employee_answers", "assignment_id", "assignment"),
    ("compliance_reports", "assignment_id", "assignment"),
    ("compliance_runs", "assignment_id", "assignment"),
    ("policy_exceptions", "assignment_id", "assignment"),
    ("compliance_actions", "assignment_id", "assignment"),
    ("assignment_invites", "case_id", "case"),
    ("case_assignments", "case_id", "case"),
    ("case_messages", "case_id", "case"),
    ("case_events", "case_id", "case"),
    ("case_forms", "case_id", "case"),
    ("case_participants", "case_id", "case"),
    ("case_milestones", "case_id", "case"),
    ("notifications", "case_id", "case"),
    ("rfq_requests", "case_id", "case"),
    ("case_outcomes", "case_id", "case"),
    ("case_escalations", "case_id", "case"),
    ("case_notes", "case_id", "case"),
]


def scalar(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchone()[0]


def guarded(cur, sql, params=None):
    """Run a statement in a savepoint; skip if the table/column doesn't exist."""
    cur.execute("SAVEPOINT s")
    try:
        cur.execute(sql, params or ())
        n = cur.rowcount
        cur.execute("RELEASE SAVEPOINT s")
        return n
    except psycopg2.Error as e:
        cur.execute("ROLLBACK TO SAVEPOINT s")
        if e.pgcode in ("42P01", "42703"):  # undefined_table / undefined_column
            return None
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    args = ap.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_URL not set")

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    test_companies = scalar(cur, "SELECT count(*) FROM companies WHERE COALESCE(is_test,false)")
    test_profiles = scalar(cur, "SELECT count(*) FROM profiles WHERE COALESCE(is_test,false)")
    # test cases = owned by a test company OR created/owned by a test profile
    case_ids = [r[0] for r in (cur.execute(
        """SELECT id FROM relocation_cases
           WHERE company_id IN (SELECT id FROM companies WHERE COALESCE(is_test,false))
              OR hr_user_id  IN (SELECT id FROM profiles  WHERE COALESCE(is_test,false))
              OR employee_id IN (SELECT id FROM profiles  WHERE COALESCE(is_test,false))""")
        or cur.fetchall())]
    print(f"is_test companies={test_companies}  profiles={test_profiles}  test relocation_cases={len(case_ids)}")

    if not args.apply:
        print("\nDRY-RUN — counts of rows that WOULD be deleted (pass --apply to delete):")
        for table, col, src in CASE_CHILDREN:
            if src == "case":
                q = f"SELECT count(*) FROM {table} WHERE {col} = ANY(%s)"
            else:
                q = (f"SELECT count(*) FROM {table} WHERE {col} IN "
                     f"(SELECT id FROM case_assignments WHERE case_id = ANY(%s))")
            n = guarded(cur, q, (case_ids,)) if case_ids else 0
            if n:
                print(f"  {table:28} {n}")
        print(f"  relocation_cases             {len(case_ids)}")
        print(f"  profiles (is_test)           {test_profiles}")
        print(f"  companies (is_test)          {test_companies}")
        conn.rollback()
        return

    # APPLY — children → cases → profiles → companies, one transaction.
    deleted = {}
    for table, col, src in CASE_CHILDREN:
        if not case_ids:
            break
        if src == "case":
            q = f"DELETE FROM {table} WHERE {col} = ANY(%s)"
        else:
            q = (f"DELETE FROM {table} WHERE {col} IN "
                 f"(SELECT id FROM case_assignments WHERE case_id = ANY(%s))")
        n = guarded(cur, q, (case_ids,))
        if n:
            deleted[table] = n
    if case_ids:
        deleted["relocation_cases"] = guarded(cur, "DELETE FROM relocation_cases WHERE id = ANY(%s)", (case_ids,))
    deleted["profiles"] = guarded(cur, "DELETE FROM profiles WHERE COALESCE(is_test,false)")
    deleted["companies"] = guarded(cur, "DELETE FROM companies WHERE COALESCE(is_test,false)")

    # verify in the same txn before committing
    left_c = scalar(cur, "SELECT count(*) FROM companies WHERE COALESCE(is_test,false)")
    left_p = scalar(cur, "SELECT count(*) FROM profiles WHERE COALESCE(is_test,false)")
    if left_c or left_p:
        conn.rollback()
        sys.exit(f"✗ verify failed (companies={left_c} profiles={left_p}) — rolled back")
    conn.commit()
    print("\n✔ purged is_test data:")
    for t, n in deleted.items():
        if n:
            print(f"  {t:28} {n}")
    print(f"✔ verified: is_test companies=0, profiles=0")


if __name__ == "__main__":
    main()
