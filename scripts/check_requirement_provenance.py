#!/usr/bin/env python3
"""
Guard: a requirement we SERVE must not claim a provenance it does not have.

WHY THIS EXISTS

`requirements_builder` serves rows with `review_status='approved'`. Measured on prod
2026-08-20: 89 served rows, and 29 of them carried NO citation at all. Every one of
those 29 was `verification_status='representative'` — a status that
`backend/app/services/disclaimers.py` defines as:

    "Items are curated + cited ("representative") but not yet signed off by a
     licensed immigration lawyer ("expert_verified")."

So they advertised a provenance level whose own definition they failed. A German
employee saw 8 requirements, 7 of which cited nothing. That is the exact claim the
product rests on — "grounded in the customer's own policy and cited" — and it was
false for a third of what we served.

WHY A DATABASE CHECK, NOT A STATIC ONE

`scripts/check_form_template_honesty.py` deliberately parses `supabase/migrations/*.sql`
from disk, and explains why: migrations are the authoring surface for form templates, so
a static check fails the PR that ADDS a bad one and needs no secret.

requirement_items is the opposite case and the same reasoning gives the opposite answer.
Exactly ONE migration in the tree inserts into it. The rows arrive instead through
`scripts/import_otto_facts.py`, `scripts/ingest_immigration_seed.py`,
`scripts/seed_additional_countries.py` and operator-run loads — so the DATABASE is the
authoring surface, and a static check would cover almost nothing. Hence: query prod,
gated on the same read-only secret the RLS-coverage and migration-drift jobs use, and
no-op where that secret is absent.

WHAT IT FLAGS

A row that is ALL THREE of:
  * review_status = 'approved'      (i.e. actually served)
  * citations_json empty/absent
  * id not present in the baseline

WHAT IT DELIBERATELY DOES NOT FLAG

  * `review_status='pending'` rows with no citation. Not served; being uncited is
    correct for a candidate. Demoting is a legitimate fix, so the guard must not
    punish it.
  * Rows whose citation is a bare UUID or an `immigration_rule.*` key rather than a
    URL. Three citation formats coexist in this column (35 raw URLs, 14
    source_records UUIDs, 10 corpus refs, on 2026-08-20) and all three resolve. A
    checker that demanded one format would flag 24 legitimate rows and be switched
    off within a day.
  * `verification_status` values other than representative. Elevating a row is a
    human decision; this guard is about the floor, not the ceiling.

The 29 pre-existing rows are listed in `requirement_provenance_baseline.txt`. The guard
exists to stop that set GROWING. It also reports baseline ids that no longer violate, so
the file cannot silently rot into an amnesty for rows that were fixed long ago.
"""
from __future__ import annotations

import os
import sys

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "requirement_provenance_baseline.txt")

VIOLATION_SQL = """
    SELECT id, country_code, title
      FROM public.requirement_items
     WHERE review_status = 'approved'
       AND (citations_json IS NULL OR citations_json::text IN ('[]', 'null', '{}'))
     ORDER BY country_code, title
"""


def load_baseline(path: str = BASELINE) -> set[str]:
    out: set[str] = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                out.add(line)
    return out


def evaluate(rows, baseline):
    """Pure: (violating rows, baseline) -> (new_violations, now_clean_baseline_ids).

    Split out so the test can exercise it without a database.
    """
    seen = {r[0] for r in rows}
    new = [r for r in rows if r[0] not in baseline]
    now_clean = sorted(baseline - seen)
    return new, now_clean


def main() -> int:
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("RLS_COVERAGE_DATABASE_URL")
    if not db_url:
        print("No read-only DATABASE_URL configured — skipping requirement-provenance check.")
        print("(Same gating as the RLS-coverage and migration-drift jobs.)")
        return 0

    try:
        import psycopg2
    except ImportError:
        print("::error::psycopg2 is required for the requirement-provenance check.")
        return 2

    baseline = load_baseline()
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(VIOLATION_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    new, now_clean = evaluate(rows, baseline)

    print(f"served-but-uncited rows: {len(rows)}   baseline: {len(baseline)}   new: {len(new)}")

    if now_clean:
        print(f"\n{len(now_clean)} baseline id(s) no longer violate — prune them from")
        print(f"{os.path.basename(BASELINE)} so the baseline keeps shrinking:")
        for rid in now_clean:
            print(f"  {rid}")

    if new:
        print("\n::error::These requirements are SERVED (review_status='approved') with no citation:")
        for rid, country, title in new:
            print(f"  {rid}  {country} — {title}")
        print("\nrequirements_builder serves approved rows, so each of these reaches a real user")
        print("as an authoritative requirement with nothing behind it. disclaimers.py defines")
        print("'representative' as curated AND CITED — an uncited served row fails its own status.")
        print("\nFix by ONE of:")
        print("  * add a real citation — a verified official URL, a source_records uuid, or an")
        print("    immigration_rule.* corpus ref. Never invent one: a fabricated citation is")
        print("    worse than a blank, because it survives review.")
        print("  * set review_status='pending' so it stops being served.")
        print("\nDo NOT add the id to the baseline to make this pass. The baseline is the frozen")
        print("2026-08-20 debt, not a suppression list.")
        return 1

    print("OK — no new served-but-uncited requirements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
