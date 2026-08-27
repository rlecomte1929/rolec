#!/usr/bin/env python3
"""
Purge E2E test data — everything tagged `is_test = true`.

Pre-launch there are no real customers, but we still scope strictly to the
durable `is_test` flag (set automatically for @testco.com / @probe.test on
companies + profiles). That predicate deliberately does NOT match the
@testcompany.com / @*-demo.com demo tenants, so a purge can never touch demo
or real data.

It also clears test accounts in `public.users` and `auth.users` (which have no
`is_test` column) by the reserved synthetic domains `@testco.com` / `@probe.test`
— these were previously left behind by the is_test-only purge, so auth/users rows
accumulated run-over-run (AIQ-1383).

`auth.users` was long assumed to need an elevated role. It does NOT. Measured
2026-08-27: the bulk delete was aborting on 23503, because `quote_messages.sender_user_id`
-> auth.users(id) is ON DELETE NO ACTION and 125 rows still referenced test users. It is
ONE statement, so those 125 rows took all 2,692 with them, and guarded() swallowed 23503
and 42501 identically — leaving "needs elevated role" printed as a hard-coded guess for
five weeks while the job exited 0.

Two consequences, both now fixed: the auth.users id space is bound separately from
public.users (they are different id spaces under the hybrid auth model), and residual rows
FAIL the run under --strict (the default) instead of being reported as a success.

SAFE BY DEFAULT: runs in --dry-run mode (counts only). Pass --apply to delete.
Deletes children before parents (no FK CASCADE in this schema), inside one
transaction, then verifies the is_test + test-domain user counts are 0.

AGE GUARD (AIQ-1593): --min-age-hours N protects is_test rows younger than N hours, so
the push-triggered E2E campaign (which runs this on every merge to main) never wipes a
live test-drive tester's account/case mid-run. Default 0 = purge everything, for the
manual full teardown (e2e-purge.yml). It only ANDs a restrictive condition, so a guarded
run never deletes MORE than an unguarded one.

Usage:
    DATABASE_URL=postgres://... python3 scripts/e2e_purge.py                      # dry-run, purge-all
    DATABASE_URL=postgres://... python3 scripts/e2e_purge.py --apply              # delete everything
    DATABASE_URL=postgres://... python3 scripts/e2e_purge.py --apply --min-age-hours 24  # keep <24h
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


# [AIQ-1737·1] case_assignments carries canonical_case_id alongside case_id. Purging by
# case_id ALONE leaves a surviving assignment whose canonical points at a now-deleted case
# → a DANGLING canonical (the drift checker's second bad shape). Match BOTH keys wherever
# the purge selects assignments, so no assignment referencing a purged case can survive.
# ARRAY[...] && %s::text[] is the case_id-OR-canonical overlap (NULL canonical is ignored),
# bound with the SAME single case-id array param the other ANY(%s) deletes already use.
_ASSIGNMENT_CASE_MATCH = "ARRAY[case_id::text, canonical_case_id::text] && %s::text[]"
_ASSIGNMENT_IDS_SUBQ = f"SELECT id::text FROM case_assignments WHERE {_ASSIGNMENT_CASE_MATCH}"


def _case_child_where(table: str, col: str, src: str) -> str:
    """WHERE clause selecting the case-child rows to purge for the bound case-id array
    (one %s ::text[]). case_assignments is matched canonical-aware (case_id OR
    canonical_case_id); assignment-scoped children resolve through the same canonical-aware
    set, so neither the assignment nor its children can be orphaned by the purge."""
    if table == "case_assignments":
        return _ASSIGNMENT_CASE_MATCH
    if src == "case":
        return f"{col}::text = ANY(%s)"
    return f"{col}::text IN ({_ASSIGNMENT_IDS_SUBQ})"


# Reserved synthetic test-email domains (mirrors backend/db/test_data_filter.py
# _TEST_EMAIL_DOMAINS). public.users has no is_test column and auth.users lives in
# the auth schema, so test accounts there are matched by these reserved domains —
# which deliberately exclude the @testcompany.com / @*-demo.com demo tenants.
TEST_EMAIL_DOMAINS = ("@testco.com", "@probe.test")
TEST_EMAIL_PREDICATE = "(" + " OR ".join(f"email ILIKE '%{d}'" for d in TEST_EMAIL_DOMAINS) + ")"


def scalar(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchone()[0]


def scalar_guarded(cur, sql):
    """scalar() in a savepoint — returns None instead of aborting the tx if the
    table/column is missing or the role lacks privilege (e.g. auth.users)."""
    cur.execute("SAVEPOINT sg")
    try:
        cur.execute(sql)
        v = cur.fetchone()[0]
        cur.execute("RELEASE SAVEPOINT sg")
        return v
    except psycopg2.Error:
        cur.execute("ROLLBACK TO SAVEPOINT sg")
        return None


# Every swallow guarded() performs, with the pgcode that caused it. For five weeks the
# purge printed "needs elevated role" while the real cause was a foreign key, because
# 23503 and 42501 both became a bare `return None`. Recording the code is what makes the
# next under-delivery diagnosable instead of a guess.
_SWALLOWED: list = []


def swallowed():
    """The swallow log, in the order the statements ran."""
    return list(_SWALLOWED)


def reset_swallowed():
    _SWALLOWED.clear()


def guarded(cur, sql, params=None, label=None):
    """Run a statement in a savepoint; tolerate missing table/column AND a foreign-key
    violation (the row is still referenced — a later cascade pass will clear it).

    A tolerated failure is RECORDED in `_SWALLOWED` with its pgcode, so the summary can
    say which of the four tolerated causes actually fired.
    """
    cur.execute("SAVEPOINT s")
    try:
        # Pass NO params arg when there are none — `params or ()` (an empty tuple)
        # still puts psycopg2 into %-interpolation mode, which chokes on a literal
        # `%` in the SQL (e.g. the ILIKE patterns in TEST_EMAIL_PREDICATE,
        # '%@testco.com') → IndexError: tuple index out of range.
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        n = cur.rowcount
        cur.execute("RELEASE SAVEPOINT s")
        return n
    except psycopg2.Error as e:
        cur.execute("ROLLBACK TO SAVEPOINT s")
        # undefined_table / undefined_column / fk_violation / insufficient_privilege
        # (42501: e.g. the app role can't delete from the auth schema — the one-time
        # prod purge runs via an elevated role; here it's a tolerated no-op).
        if e.pgcode in ("42P01", "42703", "23503", "42501"):
            _SWALLOWED.append({
                "label": label or sql.split()[2] if len(sql.split()) > 2 else (label or "?"),
                "pgcode": e.pgcode,
                "constraint": getattr(getattr(e, "diag", None), "constraint_name", None),
            })
            return None
        raise


def referencing_fks(cur, referenced):
    """Return (referencing_table, referencing_col, referenced_schema, referenced_table)
    for every FK pointing at any of the `referenced` tables.

    The schema is NOT decoration. `ccu.table_name` alone cannot tell `public.users` from
    `auth.users`, and this repo has both. Binding the wrong one is the bug that left 2,692
    test auth.users rows behind: the FK quote_messages.sender_user_id -> auth.users(id) was
    discovered, then cascaded against public.users ids, which under the hybrid auth model
    are a different id space entirely.
    """
    cur.execute(
        """SELECT tc.table_name, kcu.column_name, ccu.table_schema, ccu.table_name
           FROM information_schema.table_constraints tc
           JOIN information_schema.key_column_usage kcu
             ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
           JOIN information_schema.constraint_column_usage ccu
             ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
           WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
             AND ccu.table_name = ANY(%s)""",
        (referenced,),
    )
    return cur.fetchall()


def build_referrer_ops(fk_rows, id_queries, skip=("profiles", "companies", "users")):
    """Turn FK rows into DELETE ops, each bound to the id query for the schema+table it
    actually references.

    `id_queries` is keyed on (referenced_schema, referenced_table). A referent with no
    entry yields NO op — an unknown FK is skipped, never guessed at with the closest
    available id set, which is precisely how the auth/public mix-up went unnoticed.
    """
    ops = []
    for tbl, col, ref_schema, ref_table in fk_rows:
        if tbl in skip:
            continue
        idq = id_queries.get((ref_schema, ref_table))
        if idq is None:
            continue
        ops.append((tbl, f"DELETE FROM {tbl} WHERE {col}::text IN ({idq})", None))
    return ops


def exit_code(residual, strict):
    """0 clean; 1 when rows we meant to delete survived and --strict is on.

    The run that left 2,692 auth.users rows exited 0 and was read as a success. Residual
    is under-delivery, and under-delivery must be loud."""
    return 1 if (residual and strict) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument(
        "--min-age-hours", type=int, default=0, metavar="N",
        help="protect is_test data younger than N hours (in-flight test-drive testers). "
             "0 (default) = purge everything, for the manual full teardown; the push-triggered "
             "E2E campaign passes a positive value so a live tester is never wiped mid-run.",
    )
    ap.add_argument(
        "--no-strict", dest="strict", action="store_false", default=True,
        help="warn instead of failing when rows we meant to delete survive. Strict is ON "
             "by default: the run that left 2,692 auth.users rows exited 0 for five weeks "
             "and was read as a success every time.",
    )
    args = ap.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_URL not set")

    # AIQ-1593: age guard. The E2E campaign runs this on every push to main; without a
    # guard it deletes a live test-drive tester's account + case mid-run (a session was
    # observed deleted ~7 min old). --min-age-hours>0 appends a restrictive
    # `created_at < cutoff` to each base is_test selector so recently-created rows survive.
    # It only ever ANDs a condition, so a guarded run can never delete MORE than an
    # unguarded one. N is an int (argparse) → inlining the interval is injection-safe.
    # Applied to companies/profiles/users/auth.users and both case tables (all have
    # created_at, verified). The manual teardown (e2e-purge.yml) keeps the default 0.
    # created_at is timestamptz on companies/profiles/users/auth.users but TEXT (ISO strings)
    # on relocation_cases/cases — so cast to ::timestamptz (no-op on real timestamps, parses
    # the ISO text). A NULL/unparseable created_at makes the comparison NULL → the row is
    # EXCLUDED from the delete (protected) — the fail-safe direction.
    AGE = ""
    if args.min_age_hours and args.min_age_hours > 0:
        AGE = f" AND created_at::timestamptz < now() - make_interval(hours => {int(args.min_age_hours)})"
        print(f"age guard: protecting is_test rows newer than {args.min_age_hours}h")

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    test_companies = scalar(cur, f"SELECT count(*) FROM companies WHERE COALESCE(is_test,false){AGE}")
    test_profiles = scalar(cur, f"SELECT count(*) FROM profiles WHERE COALESCE(is_test,false){AGE}")
    # test cases = owned by a test company OR created/owned by a test profile
    # cast to ::text on both sides — relocation_cases.company_id is text while
    # companies.id is uuid (and the profile FKs vary), so a bare IN raises
    # "operator does not exist: text = uuid".
    # There are TWO case tables — relocation_cases (hr_user_id) and public.cases
    # (hr_owner_id). Collect is_test-owned ids from BOTH (::text both sides).
    cur.execute(
        f"""SELECT id::text FROM relocation_cases
             WHERE (company_id::text IN (SELECT id::text FROM companies WHERE COALESCE(is_test,false))
                OR hr_user_id::text  IN (SELECT id::text FROM profiles  WHERE COALESCE(is_test,false))
                OR employee_id::text IN (SELECT id::text FROM profiles  WHERE COALESCE(is_test,false))){AGE}
           UNION
           SELECT id::text FROM cases
             WHERE (company_id::text  IN (SELECT id::text FROM companies WHERE COALESCE(is_test,false))
                OR hr_owner_id::text IN (SELECT id::text FROM profiles  WHERE COALESCE(is_test,false))
                OR employee_id::text IN (SELECT id::text FROM profiles  WHERE COALESCE(is_test,false))){AGE}""")
    case_ids = [r[0] for r in cur.fetchall()]
    # [AIQ-1383] testco COMPANIES are not is_test-flagged (only profiles/people are), so the
    # is_test-only companies delete below misses them → orphan accumulation. Capture them by their
    # @testco.com profile link NOW, before the profiles are deleted (companies are deleted last).
    cur.execute(
        f"SELECT DISTINCT company_id::text FROM profiles "
        f"WHERE company_id IS NOT NULL AND {TEST_EMAIL_PREDICATE}{AGE}")
    testco_company_ids = [r[0] for r in cur.fetchall()]
    print(f"is_test companies={test_companies}  profiles={test_profiles}  test cases (both tables)={len(case_ids)}"
          f"  testco companies (by email link)={len(testco_company_ids)}")

    if not args.apply:
        print("\nDRY-RUN — counts of rows that WOULD be deleted (pass --apply to delete):")
        for table, col, src in CASE_CHILDREN:
            q = f"SELECT count(*) FROM {table} WHERE {_case_child_where(table, col, src)}"
            n = guarded(cur, q, (case_ids,)) if case_ids else 0
            if n:
                print(f"  {table:28} {n}")
        print(f"  cases (both tables)          {len(case_ids)}")
        print(f"  + FK-cascade of every table referencing the is_test profiles/companies")
        print(f"  profiles (is_test)           {test_profiles}")
        print(f"  companies (is_test)          {test_companies}")
        print(f"  companies (by @testco link)  {len(testco_company_ids)}")
        # public.users + auth.users test accounts (matched by reserved domains, not
        # is_test — those tables have no such column). auth.users may read as n/a if
        # the role can't see the auth schema (the elevated one-time purge handles it).
        users_test = scalar_guarded(cur, f"SELECT count(*) FROM public.users WHERE {TEST_EMAIL_PREDICATE}{AGE}")
        auth_test = scalar_guarded(cur, f"SELECT count(*) FROM auth.users WHERE {TEST_EMAIL_PREDICATE}{AGE}")
        print(f"  public.users (test domains)  {users_test if users_test is not None else 'n/a'}")
        print(f"  auth.users (test domains)    {auth_test if auth_test is not None else 'n/a (no auth-schema perm)'}")
        conn.rollback()
        return 0

    # APPLY — one transaction. case children → both case tables → FK-derived cascade
    # of everything referencing the is_test profiles/companies → the profiles/companies.
    deleted: dict = {}

    def bump(t, n):
        if n:
            deleted[t] = deleted.get(t, 0) + n

    # Build every delete as (label, sql, params): case children, both case tables,
    # and every table referencing the is_test profiles/companies (from the live FK
    # graph). Run them all in ONE fixed-point loop — guarded() tolerates an FK
    # violation, so an op simply retries on a later pass once its children are gone.
    prof_q = f"SELECT id::text FROM profiles WHERE COALESCE(is_test,false){AGE}"
    comp_q = f"SELECT id::text FROM companies WHERE COALESCE(is_test,false){AGE}"
    users_q = f"SELECT id::text FROM users WHERE {TEST_EMAIL_PREDICATE}{AGE}"
    ops = []
    for table, col, src in CASE_CHILDREN:
        ops.append((table, f"DELETE FROM {table} WHERE {_case_child_where(table, col, src)}", (case_ids,)))
    ops.append(("relocation_cases", "DELETE FROM relocation_cases WHERE id::text = ANY(%s)", (case_ids,)))
    ops.append(("cases", "DELETE FROM cases WHERE id::text = ANY(%s)", (case_ids,)))
    # auth.users is a SEPARATE id space from public.users under the hybrid auth model.
    # Its referrers (quote_messages.sender_user_id, quote_participants, vendor_users — all
    # ON DELETE NO ACTION) must be cleared with auth ids, or the bulk auth.users delete
    # aborts on 23503 and takes every other row with it: one statement, all-or-nothing.
    auth_q = f"SELECT id::text FROM auth.users WHERE {TEST_EMAIL_PREDICATE}{AGE}"
    id_queries = {
        ("public", "profiles"): prof_q,
        ("public", "companies"): comp_q,
        ("public", "users"): users_q,
        ("auth", "users"): auth_q,
    }
    ops += build_referrer_ops(referencing_fks(cur, ["profiles", "companies", "users"]), id_queries)
    # any table referencing either case table (catches case-children not hardcoded above)
    for tbl, col, _ref_schema, _ref_table in referencing_fks(cur, ["relocation_cases", "cases"]):
        if tbl not in ("profiles", "companies", "relocation_cases", "cases"):
            ops.append((tbl, f"DELETE FROM {tbl} WHERE {col}::text = ANY(%s)", (case_ids,)))

    for _ in range(10):
        progressed = False
        for label, sql, params in ops:
            n = guarded(cur, sql, params)
            if n:
                bump(label, n)
                progressed = True
        if not progressed:
            break

    # finally the profiles + companies themselves (best effort — tolerate residual FK).
    bump("profiles", guarded(cur, f"DELETE FROM profiles WHERE COALESCE(is_test,false){AGE}"))
    # [AIQ-1383] is_test-flagged OR a testco company captured by email link above (empty ANY → no-op).
    # AGE binds tighter than OR, so this is (is_test AND old) OR (testco id); testco_company_ids
    # is itself already age-filtered above, so recent testers survive both branches.
    bump("companies", guarded(
        cur,
        f"DELETE FROM companies WHERE COALESCE(is_test,false){AGE} OR id::text = ANY(%s)",
        (testco_company_ids,),
    ))

    # ...and the test accounts in public.users + auth.users (matched by reserved
    # domains). public.users children were cascaded in the loop above; deleting
    # auth.users also cascades auth.* (identities/sessions) + any test profile.
    # guarded(): a no-perm auth delete (app role) is a tolerated no-op — the
    # elevated one-time purge clears auth.users.
    bump("users", guarded(cur, f"DELETE FROM public.users WHERE {TEST_EMAIL_PREDICATE}{AGE}",
                          label="public.users"))
    # identities first — scripts/reset_demo.sh has always done this; the purge did not.
    # (auth.identities is ON DELETE CASCADE, so this is belt-and-braces, not load-bearing.)
    bump("auth.identities", guarded(cur, f"DELETE FROM auth.identities WHERE user_id::text IN ({auth_q})",
                                    label="auth.identities"))
    bump("auth.users", guarded(cur, f"DELETE FROM auth.users WHERE {TEST_EMAIL_PREDICATE}{AGE}",
                               label="auth.users"))

    # Verify against the SAME scope we deleted (age-guarded), so "0 remaining" means
    # "every row we intended to delete is gone" — recent protected rows are expected to stay.
    left_c = scalar(cur, f"SELECT count(*) FROM companies WHERE COALESCE(is_test,false){AGE}")
    left_p = scalar(cur, f"SELECT count(*) FROM profiles WHERE COALESCE(is_test,false){AGE}")
    left_u = scalar_guarded(cur, f"SELECT count(*) FROM public.users WHERE {TEST_EMAIL_PREDICATE}{AGE}")
    left_a = scalar_guarded(cur, f"SELECT count(*) FROM auth.users WHERE {TEST_EMAIL_PREDICATE}{AGE}")
    conn.commit()
    print("\n✔ purged is_test data:")
    for t, n in sorted(deleted.items(), key=lambda kv: -kv[1]):
        if n:
            print(f"  {t:28} {n}")
    residual = []
    if left_c or left_p:
        residual.append(f"companies={left_c} profiles={left_p}")
    if left_u:
        residual.append(f"public.users={left_u}")
    if left_a:
        residual.append(f"auth.users={left_a}")
    # Report the ACTUAL cause rather than the old hard-coded "needs elevated role" guess.
    swallows = swallowed()
    if swallows:
        print("\nswallowed (tolerated) failures — this is the diagnosis:")
        for rec in swallows:
            why = {
                "23503": "foreign key still referencing",
                "42501": "insufficient privilege",
                "42P01": "table does not exist",
                "42703": "column does not exist",
            }.get(rec["pgcode"], rec["pgcode"])
            where = f" [{rec['constraint']}]" if rec.get("constraint") else ""
            print(f"  {rec['label']:28} {rec['pgcode']}  {why}{where}")
    if residual:
        print(f"⚠ residual test rows remain ({'; '.join(residual)})")
        if args.strict:
            print("::error::purge under-delivered — see the swallowed-failures list above")
        return exit_code(residual, args.strict)
    print("✔ verified: is_test companies=0, profiles=0, test users/auth=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
