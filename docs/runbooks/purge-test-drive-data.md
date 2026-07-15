# Runbook — Purge test-drive data (AIQ-1545)

Reset test-drive data between waves without touching real records.

Script: `backend/scripts/purge_test_drive_data.py` (run from repo root; needs `DATABASE_URL`).

## What it deletes

| Target | Scope |
|---|---|
| `test_sessions`, `survey_responses`, `funnel_events` | **all rows** — these tables exist only for the test-drive campaign |
| `feedback` | rows where `campaign IS NOT NULL` (only the test-drive flow stamps `campaign`) |
| `profiles`, `companies` (`--include-tenants` only) | rows where `is_test = true` |

Real rows are never in scope. The script snapshots the real (non-test) counts before and after
and **aborts + rolls back** if any changed.

## How to run

```bash
# 1. Always dry-run first — reports what WOULD be deleted, deletes nothing.
python -m backend.scripts.purge_test_drive_data

# 2. Purge the test-drive tables (sessions/surveys/funnel/feedback).
python -m backend.scripts.purge_test_drive_data --execute

# 3. Also remove the synthetic tenants (is_test companies/profiles). Opt-in — see caveat.
python -m backend.scripts.purge_test_drive_data --execute --include-tenants
```

Re-running is safe (idempotent) — a second run deletes 0 rows.

## Caveats

- `--include-tenants` is **off by default**. `companies`/`profiles` are shared tables and their
  FK dependents (`relocation_cases`, `case_assignments`, …) carry **no `is_test` marker**, so a
  dependent row can FK-block the delete. The script reports blocked targets and leaves them in
  place rather than force-cascading — clean up dependents first, or rely on the read-time
  exclusion (`backend/db/test_data_filter.py`) which already hides them from admin surfaces.
- Provisioned tester login accounts in the legacy `public.users` table are **not** purged by
  this script (no `is_test` marker there); they are harmless and re-used across waves.
