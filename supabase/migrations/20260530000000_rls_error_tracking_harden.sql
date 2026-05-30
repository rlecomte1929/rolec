-- SEC-RLSe (AIQ-662) — finalize RLS on error_logs / error_tickets so they can
-- leave rls_allowlist.txt (Path B).
--
-- These two tables are read (and error_tickets updated) DIRECTLY by the frontend
-- admin UI via the anon/authenticated Supabase-JS client
-- (frontend/src/components/admin/ErrorTicketsTab.tsx → supabase.from('error_logs'|'error_tickets')).
-- They are therefore NOT server-role-only and need real RLS policies.
--
-- 20260502100000_error_tracking_tables.sql already enabled RLS and added admin
-- SELECT (both) + admin UPDATE (error_tickets) policies gated on
-- profiles.role = 'ADMIN', but OMITTED `REVOKE anon` (defense-in-depth).
--
-- This migration is self-contained and idempotent: it re-asserts RLS + the
-- profiles-based admin policies (so the end state holds even if the baseline
-- migration has not been applied to the target DB) and adds the missing anon
-- revoke. The admin gate is profiles.role = 'ADMIN' — the mechanism already in
-- use for these tables. (public.admin_allowlist is email-keyed and is not the
-- gate used here.)
--
-- Reversible — see rollback notes at the end of the file.

-- 1. Ensure RLS is enabled (idempotent).
alter table public.error_logs    enable row level security;
alter table public.error_tickets enable row level security;

-- 2. Re-assert the admin read/update policies (same names + expressions as the
--    baseline, so applying in either order yields a single canonical policy set).
drop policy if exists "admin can read error_logs" on public.error_logs;
create policy "admin can read error_logs"
  on public.error_logs for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id = auth.uid()::text
        and profiles.role = 'ADMIN'
    )
  );

drop policy if exists "admin can read error_tickets" on public.error_tickets;
create policy "admin can read error_tickets"
  on public.error_tickets for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id = auth.uid()::text
        and profiles.role = 'ADMIN'
    )
  );

drop policy if exists "admin can update error_tickets" on public.error_tickets;
create policy "admin can update error_tickets"
  on public.error_tickets for update
  using (
    exists (
      select 1 from public.profiles
      where profiles.id = auth.uid()::text
        and profiles.role = 'ADMIN'
    )
  );

-- 3. Defense-in-depth: strip any direct grants to the public anon key.
--    (RLS already blocks anon, but the anon key ships in the frontend bundle.)
revoke all on public.error_logs    from anon;
revoke all on public.error_tickets from anon;

-- ── Rollback ─────────────────────────────────────────────────────────────────
-- The policies above are identical to 20260502100000 and can be left in place.
-- To restore anon grants (not recommended):
--   grant select on public.error_logs, public.error_tickets to anon;
