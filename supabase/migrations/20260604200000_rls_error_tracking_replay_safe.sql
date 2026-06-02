-- Replay-safe recreation of the error_logs / error_tickets admin policies.
--
-- The original SEC-RLSe migration (20260530000000_rls_error_tracking_harden.sql)
-- used a `profiles.id = auth.uid()::text` predicate that fails on the uuid
-- `profiles.id` column (ERROR 42883), aborting any fresh `supabase db reset`.
-- That file is now a documentary no-op; #212
-- (20260601130000_fix_rls_error_harden_uuid_cast.sql) applied the correct
-- policies fix-forward to prod.
--
-- This migration recreates those same three policies with the canonical cast
-- `profiles.id::uuid = auth.uid()`, copied byte-for-byte from #212, so a fresh
-- replay reaches the same end-state prod is already in. Idempotent via
-- DROP POLICY IF EXISTS — a true no-op on prod.
-- See audit/194-replay-landmine-2026-06-02.md.

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
