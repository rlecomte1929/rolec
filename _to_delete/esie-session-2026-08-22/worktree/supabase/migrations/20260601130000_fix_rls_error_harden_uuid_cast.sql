-- Fixes 20260530000000_rls_error_tracking_harden.sql — uuid/text type mismatch
-- on the profiles.id comparison.
--
-- The original SEC-RLSe (AIQ-662) migration gated the error_logs / error_tickets
-- admin policies on `profiles.id = auth.uid()::text`. In production `profiles.id`
-- is `uuid`, so that comparison raises:
--     ERROR 42883: operator does not exist: uuid = text
-- and the three policies never applied (the apply was transactional and rolled
-- back cleanly — verified: error_logs/error_tickets have RLS enabled, 0 policies,
-- and anon already revoked).
--
-- This migration re-creates the three policies with the codebase-canonical cast
-- `profiles.id::uuid = auth.uid()` (the convention established by main commits
-- 470cb584 / 95b97304). It does NOT re-assert ENABLE RLS or REVOKE anon — those
-- already hold in production and were untouched by the failed transaction.

-- Drop the (never-applied, but idempotent) original policy names, then re-create
-- with the corrected cast direction.
drop policy if exists "admin can read error_logs" on public.error_logs;
create policy "admin can read error_logs"
  on public.error_logs for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id::uuid = auth.uid()
        and profiles.role = 'ADMIN'
    )
  );

drop policy if exists "admin can read error_tickets" on public.error_tickets;
create policy "admin can read error_tickets"
  on public.error_tickets for select
  using (
    exists (
      select 1 from public.profiles
      where profiles.id::uuid = auth.uid()
        and profiles.role = 'ADMIN'
    )
  );

drop policy if exists "admin can update error_tickets" on public.error_tickets;
create policy "admin can update error_tickets"
  on public.error_tickets for update
  using (
    exists (
      select 1 from public.profiles
      where profiles.id::uuid = auth.uid()
        and profiles.role = 'ADMIN'
    )
  );
