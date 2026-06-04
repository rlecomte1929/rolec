-- ============================================================================
-- P2-01a (AIQ) · Backend-native feature flags
--
-- Establishes a DB-backed feature-flag mechanism so backend behaviour can be
-- toggled without a redeploy, scoped to an allowlist of selected accounts.
-- First consumer: the live AI EEA roadmap (France → Norway), gated in
-- backend/app/routers/cases_read.py:get_case_roadmap.
--
-- A flag is active for an account only when feature_flags.enabled is true AND a
-- matching (flag_key, account_id) row exists in feature_flag_accounts.
--
-- Tenancy / security: these tables are read ONLY by the FastAPI backend, which
-- connects via DATABASE_URL as the `postgres` role and therefore bypasses RLS.
-- They are NOT read by the frontend through the Supabase anon client. RLS here
-- is the SEC-002 defense-in-depth boundary: deny the public anon key (shipped
-- in the frontend bundle) any access via PostgREST. Pattern reference:
-- 20260601000000_rls_cases_domain.sql.
--
-- Reversible: see the rollback block at the foot of this file.
-- ============================================================================

begin;

create table if not exists public.feature_flags (
  key         text primary key,
  enabled     boolean     not null default false,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists public.feature_flag_accounts (
  flag_key   text        not null references public.feature_flags(key) on delete cascade,
  account_id text        not null,
  created_at timestamptz not null default now(),
  primary key (flag_key, account_id)
);

-- --- RLS: enable + deny all non-superuser roles (backend connects as postgres
-- --- and bypasses RLS; service role likewise). No anon/authenticated access.
alter table public.feature_flags         enable row level security;
alter table public.feature_flag_accounts enable row level security;

revoke all on public.feature_flags         from anon, authenticated;
revoke all on public.feature_flag_accounts from anon, authenticated;

-- At least one explicit policy documenting the "no client access" boundary
-- (satisfies the hard review gate; deny-by-default for anon/authenticated).
create policy "feature_flags service-only" on public.feature_flags
  for all using (false) with check (false);
create policy "feature_flag_accounts service-only" on public.feature_flag_accounts
  for all using (false) with check (false);

-- Seed the live EEA roadmap flag, DISABLED by default. Go-live (P2-01g) flips
-- this on and adds the test-account allowlist rows.
insert into public.feature_flags (key, enabled, description)
values (
  'live_eea_roadmap',
  false,
  'P2-01: serve the live AI EEA roadmap to allowlisted test accounts only'
)
on conflict (key) do nothing;

commit;

-- ============================================================================
-- Rollback (manual):
--   drop table if exists public.feature_flag_accounts;
--   drop table if exists public.feature_flags;
-- ============================================================================
