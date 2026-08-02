#!/usr/bin/env python3
"""
canonical_case_id drift check — AIQ-1731 / AIQ-1732.

`case_assignments.canonical_case_id` is the key most case-scoped reads resolve
through, but the column is **nullable with no default, no FK and no UNIQUE**
(`20260324000000_canonical_case_id_phase1.sql` adds only a plain btree index).
All three bad shapes are therefore permitted by the schema:

  * **NULL / blank**   — case-scoped reads resolve through it and find nothing
  * **dangling**       — points at neither a `relocation_cases` nor a `cases` row
  * **duplicate**      — two assignments claim the same canonical case

`docs/architecture/CASE_ID_UNIFICATION_AUDIT.md` (AIQ-1730) inventoried the prod
stock and returned the verdict *the model is 1:1, so `UNIQUE(canonical_case_id)`
is the right constraint*. Cleaning that stock (AIQ-1731) and enforcing the
constraint (AIQ-1732) are **deliberately deferred** to the pre-launch data reset,
because the cleanup means ~38 cascading deletes of throwaway pre-launch data for
a constraint the `resolve_case_ids` bridge already substitutes for.

The deferral is only safe while the stock stays **frozen**. This check is that
tripwire: it compares live prod against a committed baseline of the known-bad
assignment ids and fails on **new** violations only — never on the frozen stock.
When the deferred cleanup finally runs, cleaned ids simply drop out of the live
set and the baseline shrinks via ``--update-baseline``.

Exit codes:
  0 — no violation outside the baseline (or none at all)
  1 — at least one NEW bad row (CI should fail)
  2 — could not connect to DB or query failed (unexpected — investigate)

Usage:
  DATABASE_URL=postgresql://... python scripts/check_canonical_case_id_drift.py
  DATABASE_URL=postgresql://... python scripts/check_canonical_case_id_drift.py --json
  DATABASE_URL=postgresql://... python scripts/check_canonical_case_id_drift.py --update-baseline

``--update-baseline`` rewrites the baseline from the current live set. Use it
after a deliberate cleanup. **Never wire it into CI** — it would make the gate
rubber-stamp whatever drift it found (same rule as check_rls_coverage.py's
``--update-allowlist``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = REPO_ROOT / "supabase" / "canonical_case_id_baseline.txt"

# One row per offending assignment, classified with the SAME precedence the audit
# doc used (null > dangling > duplicate) so the counts here and there agree.
# CAST via ::text throughout: canonical_case_id is `text` while the id columns it
# points at are `uuid`, so an untyped comparison errors.
AUDIT_SQL = """
WITH ca AS (SELECT * FROM public.case_assignments),
cls AS (
  SELECT id::text AS assignment_id,
    CASE
      WHEN canonical_case_id IS NULL OR btrim(canonical_case_id::text) = '' THEN 'null'
      WHEN NOT EXISTS (SELECT 1 FROM public.relocation_cases rc
                        WHERE rc.id::text = ca.canonical_case_id::text)
       AND NOT EXISTS (SELECT 1 FROM public.cases c
                        WHERE c.id::text = ca.canonical_case_id::text) THEN 'dangling'
      WHEN canonical_case_id IN (
        SELECT canonical_case_id FROM ca
        WHERE canonical_case_id IS NOT NULL
        GROUP BY 1 HAVING count(*) > 1
      ) THEN 'duplicate'
      ELSE 'ok'
    END AS bucket
  FROM ca
)
SELECT assignment_id, bucket FROM cls WHERE bucket <> 'ok' ORDER BY bucket, assignment_id;
"""


def load_baseline(path: Path) -> "set[str]":
    """Known-bad assignment ids. Comments (`#`) and blank lines are ignored;
    an inline `# bucket — why` comment after an id is ignored too."""
    if not path.exists():
        return set()
    baseline: "set[str]" = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            baseline.add(line)
    return baseline


def new_violations(
    live: "Iterable[tuple[str, str]]", baseline: "set[str]"
) -> "list[tuple[str, str]]":
    """Live offenders NOT on the baseline — the rows that must FAIL the gate.

    Keyed on the assignment id alone, deliberately: a baselined row that migrates
    between buckets (a dangling canonical whose twin is later deleted becomes
    merely dangling, etc.) is not NEW badness, and re-failing on it would make the
    gate noisy while the cleanup is parked. Pure function (no DB) so the fail path
    is unit-testable.
    """
    return [(aid, bucket) for aid, bucket in live if aid not in baseline]


def stale_baseline_entries(
    live: "Iterable[tuple[str, str]]", baseline: "set[str]"
) -> "list[str]":
    """Baseline ids that are no longer bad — cleaned up, or the row is gone.
    Reported as a WARN so the baseline can be trimmed; never a failure."""
    live_ids = {aid for aid, _ in live}
    return sorted(baseline - live_ids)


def query_bad_rows(db_url: str) -> "list[tuple[str, str]]":
    try:
        import psycopg2
    except ImportError:
        print(
            "psycopg2 not installed — `pip install psycopg2-binary` or run from backend venv",
            file=sys.stderr,
        )
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

    return [(str(aid), str(bucket)) for aid, bucket in rows]


def write_baseline(path: Path, rows: "Iterable[tuple[str, str]]") -> None:
    header = (
        "# supabase/canonical_case_id_baseline.txt\n"
        "# AIQ-1731 — the KNOWN-BAD case_assignments rows that the deferred data\n"
        "# cleanup will resolve. Consulted by scripts/check_canonical_case_id_drift.py\n"
        "# in CI, which fails only on offenders NOT listed here.\n"
        "#\n"
        "# This file is a snapshot of a deferral, NOT an allowlist of acceptable\n"
        "# state. Every id here is scheduled for repair by the pre-launch data\n"
        "# reset (see docs/architecture/CASE_ID_UNIFICATION_AUDIT.md). Shrinking\n"
        "# this file is the goal; growing it means the cleanup got further away.\n"
        "#\n"
        "# Do NOT add an id here to make CI green on a NEW bad row — fix the writer.\n"
        "# Regenerate after a deliberate cleanup with:\n"
        "#   DATABASE_URL=... python scripts/check_canonical_case_id_drift.py --update-baseline\n"
        "#\n"
        "# Format: one assignment id per line. `#` starts a comment.\n"
        "\n"
    )
    by_bucket: "dict[str, list[str]]" = {}
    for aid, bucket in rows:
        by_bucket.setdefault(bucket, []).append(aid)
    body = ""
    for bucket in sorted(by_bucket):
        ids = sorted(by_bucket[bucket])
        body += f"# --- {bucket} ({len(ids)}) ---\n"
        body += "\n".join(ids) + "\n\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail on NEW canonical_case_id violations in prod."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the diff as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help=(
            "Rewrite supabase/canonical_case_id_baseline.txt from the current live "
            "set. Use after a deliberate cleanup. NEVER wire this into CI."
        ),
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    live = query_bad_rows(db_url)
    baseline = load_baseline(BASELINE_FILE)

    if args.update_baseline:
        write_baseline(BASELINE_FILE, live)
        print(
            f"[canonical-drift] wrote {len(live)} entries to "
            f"{BASELINE_FILE.relative_to(REPO_ROOT)}"
        )
        return 0

    new = new_violations(live, baseline)
    stale = stale_baseline_entries(live, baseline)
    counts: "dict[str, int]" = {}
    for _, bucket in live:
        counts[bucket] = counts.get(bucket, 0) + 1

    if args.json:
        print(json.dumps({
            "live_bad_rows": len(live),
            "by_bucket": counts,
            "baseline_total": len(baseline),
            "new_violations": [{"assignment_id": a, "bucket": b} for a, b in new],
            "stale_baseline_entries": stale,
            "pass": len(new) == 0,
        }, indent=2))
    else:
        summary = ", ".join(f"{b}={counts[b]}" for b in sorted(counts)) or "none"
        print(f"[canonical-drift] live bad case_assignments rows: {len(live)} ({summary})")
        print(f"[canonical-drift] baseline entries: {len(baseline)}")
        if new:
            print(
                f"\n[canonical-drift] FAIL — {len(new)} NEW bad row(s) not on the baseline:"
            )
            for aid, bucket in new:
                print(f"  - {aid}  ({bucket})")
            print(
                "\nA new row here means something WROTE a bad canonical_case_id — the\n"
                "deferred cleanup (AIQ-1731) is not the fix, the writer is. Check:\n"
                "  * a seed/fixture omitting canonical_case_id (it is nullable — omitting\n"
                "    it writes NULL; see scripts/seed_demo.sql and docs/ASSIGNMENT_DEBUG.md)\n"
                "  * a duplicate submit against POST /api/hr/cases/{case_id}/assign\n"
                "    (guarded by db.get_active_assignment_for_case_employee)\n"
                "  * a purge/teardown deleting cases while leaving assignments keyed on a\n"
                "    different canonical (scripts/e2e_purge.py, fresh_onboarding_teardown.sql)\n"
                "\nDo NOT add the id to the baseline to go green — that hides the regression.\n"
            )
        elif stale:
            print(
                f"\n[canonical-drift] WARN — {len(stale)} baseline entries are no longer bad:"
            )
            for aid in stale:
                print(f"  - {aid}  (safe to remove from the baseline)")
            print("\n  Trim with --update-baseline.")
        else:
            print("\n[canonical-drift] PASS — no new violations.")

    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
