-- Ledger reconciliation for `ror_coverage_ledger` (CLAUDE.md § Ledger reconciliation).
--
-- This migration was applied to production OUT OF BAND via MCP `apply_migration` on
-- 2026-08-11 at 17:08:03, which stamps its own wall-clock version. That left
-- `supabase_migrations.schema_migrations` holding version 20260811170803 with no matching
-- repo file — the exact drift that makes `check_migration_drift.py` (and any Supabase
-- Preview) fail for EVERY subsequent migration PR, not just the one that caused it.
-- Found by the 2026-08-11 guard sweep, which ran the drift check against live prod.
--
-- The SQL below is recovered verbatim from that ledger row's `statements` column, so the
-- file matches exactly what ran. It was already idempotent as applied.
--
-- Do not use `apply_migration` against production. Applies are operator-run and
-- out-of-band, then recorded with:
--   supabase migration repair --status applied <version> --db-url "$DATABASE_URL"
-- See CLAUDE.md § "Migration discipline (MANDATORY)".
--
-- RLS: these two tables were created with no RLS, no policy and no REVOKE, which the
-- "Database Migrations — Security Rules" hard gate requires for any new `public` table.
-- That is fixed forward in 20261028000000_ror_tables_rls.sql rather than by editing this
-- file, which must keep matching the applied statements.

create table if not exists public.ror_cities (
  id bigserial primary key,
  country_rank int, country text, iso2 text, region text, city text,
  city_rank int, primary_hub boolean default false, in_relopass boolean default false
);
create table if not exists public.ror_queue (
  id bigserial primary key,
  stream text not null,            -- A_immigration | B_service | C_guide
  country_code text not null,
  city text,                       -- null for country-level immigration
  unit_key text not null,          -- service category code | guide topic | 'immigration'
  priority int not null,
  status text not null default 'queued',  -- queued|launched|loaded|verified|done|skipped
  launched_at timestamptz, loaded_at timestamptz, notes text,
  created_at timestamptz default now()
);
create unique index if not exists ror_queue_uk on public.ror_queue (stream, country_code, coalesce(city,''), unit_key);
