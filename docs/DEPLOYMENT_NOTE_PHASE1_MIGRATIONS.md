# ReloPass Deployment Note — Phase 1 Supabase Migrations

**Last verified:** Mar 2025

## Phase 1 Migrations — Production Status

| Migration | Description | Status |
|-----------|-------------|--------|
| `20260321000000_case_events_phase1.sql` | case_events: add payload, actor_principal_id; update RLS | ✅ **Applied** |
| `20260322000000_case_participants.sql` | case_participants table + backfill from case_assignments | ✅ **Applied** |

## Verification

```bash
npx supabase migration list
```

Local and Remote should both list the above migrations. If Remote lags, run:

```bash
npx supabase db push
```

## Pending (Phase 1 Design, Not Yet in Migrations)

- `20260320000000_standardize_case_id_phase1.sql` — case_id type standardization; defined in MIGRATION_PHASE_1_2_DESIGN.md but migration file not present in repo.

## Operational Notes

- Backend uses `relocation_cases` for HR-created cases; `case_participants` references `wizard_cases`. Backfill only includes assignments whose `case_id` exists in `wizard_cases`; HR cases in `relocation_cases` are not backfilled.
- `ensure_case_participant` and `insert_case_event` are non-blocking in the assign flow; assignment creation succeeds even if these writes fail.
