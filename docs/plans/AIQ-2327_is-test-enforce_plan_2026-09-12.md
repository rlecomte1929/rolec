# AIQ-2327 — Enforce is_test across admin (ADMIN-IA-0b) — implementation plan

Card: https://app.notion.com/p/bbad63854de44f02b8abf9452d8999bc
Branch: `feat/admin-is-test-enforce` · Date: 2026-09-12

> Lightweight plan (full `/autoplan` not run in this batched execution).

## Approach

Extend the durable `is_test` flag (added to companies+profiles by 20260629000000) to
the tables that still had none — `leads`, `prospect_candidates`, `linkedin_prospects`,
`hr_supplier_submissions` — plus backfill the newer seeder families the AIQ-913 filter
predates. The read-time filter in `test_data_filter.py` mirrors the same patterns so the
rows are hidden **immediately** (before the migration applies); the flag is the durable
version. A header toggle re-reveals them (with a "test" badge) for debugging.

## Files

- CREATED `supabase/migrations/20261146000000_is_test_extend.sql` — column-adds (no new
  table → no RLS gate) + idempotent backfill mirroring the Aside flip-list (41 companies,
  the hotmail `+alias` signups, resend.app/example.com leads, QA prospects/suppliers).
- MODIFIED `backend/db/test_data_filter.py` — `exclude_test_companies` / `exclude_test_people`
  (read-time, LOWER+LIKE so PG+SQLite-safe) + `looks_like_test_company` / `looks_like_test_email`
  (write-time auto-stamp) extended with the new families. 'Testing April' and
  romain_lecomte@hotmail.com are provably kept.
- MODIFIED `backend/app/models.py` — `is_test` on `Lead` + `ProspectCandidate`.
- MODIFIED `backend/app/routers/admin_leads.py`, `admin_prospects.py` — `include_test` param, default filters `is_test=false`.
- MODIFIED `frontend/src/api/client.ts` — request interceptor appends `include_test=true` to admin GETs when the toggle is on (the "one place").
- MODIFIED `frontend/src/pages/admin/AdminLayout.tsx` — "Show test data" Switch (localStorage `admin_show_test_data`, default off; invalidates the query cache on toggle).
- MODIFIED `frontend/src/pages/admin/AdminCompanies.tsx` + `types.ts` — grey "test" Badge on flagged rows.
- MODIFIED `backend/tests/test_test_data_filter.py` — new cases for every AIQ-2327 pattern.

## Decisions / risks for review (step 5 [Cursor] + step 6/7)

1. **The card's table names were wrong.** Expected Output said `prospects` / `supplier_submissions`;
   the real tables are `prospect_candidates` / `hr_supplier_submissions` (verified). Handlers for
   companies/people are in `backend/main.py`, not `admin.py`. Implemented against the real schema.
2. **⚠️ Apply-ordering (step 6/7).** This branch ADDS is_test columns AND reads them (ORM
   filter `Lead.is_test`, `ProspectCandidate.is_test`). Per CLAUDE.md the column-read CI guard
   blocks "ADD COLUMN + read in one PR", and — more importantly — if the reader code deploys
   **before** the migration is applied to prod, /admin/leads and /admin/prospects will 500.
   Recommended: ship the migration alone, apply it (step 7b, with Romain's written OK), then
   merge the readers; OR make the two ORM reads column-presence-guarded like companies/profiles.
   Flagged for the step-6 owner.
3. **Migration timestamp** `20261146000000` is above both repo-max and ledger-max as of
   2026-09-12; re-verify at push time (parallel PRs may grab the same).
4. **'%test%' matching** is now applied to companies (with an explicit 'Testing April'
   exclusion) — this is the intended widening per the Aside flip-list; confirm no real tenant
   in the kept-set contains "test".

## Verification (Test Command — green 2026-09-12, fresh ci_test.db)

`pytest backend/tests -k "test_data_filter or is_test or admin_companies or leads or prospects"`
→ 28 passed. `tsc --noEmit` clean. `vitest run src/pages/admin` → 129 passed.
(Note: a stale local `ci_test.db` first failed the lead tests — `create_all` can't ALTER an
existing table; deleting it and re-running is green, and CI starts fresh.)
