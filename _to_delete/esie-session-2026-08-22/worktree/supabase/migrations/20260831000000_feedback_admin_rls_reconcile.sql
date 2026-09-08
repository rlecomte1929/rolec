-- Reconcile public.feedback admin RLS policies with production.
--
-- The original migration 20260502110000_feedback.sql declared the admin
-- SELECT/UPDATE policies as `profiles.id = auth.uid()::text`. In production
-- public.profiles.id is UUID, so that expression raises
--   ERROR 42883: operator does not exist: uuid = text
-- at CREATE POLICY time — which is why those two policies were never applied to
-- prod (only the INSERT policy landed). This migration applies the corrected,
-- type-matched expression (`profiles.id = auth.uid()`, no ::text cast — the same
-- pattern used by every other admin RLS policy in prod) so the repo matches the
-- live database. Idempotent.
--
-- Note: public.feedback is served to the app exclusively through the FastAPI
-- backend (service-role), so these PostgREST policies are defense-in-depth for
-- any future direct authenticated read/update via PostgREST.

alter table public.feedback enable row level security;

drop policy if exists "admin can read feedback" on public.feedback;
create policy "admin can read feedback"
  on public.feedback for select
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid()
        and role = 'ADMIN'
    )
  );

drop policy if exists "admin can update feedback" on public.feedback;
create policy "admin can update feedback"
  on public.feedback for update
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid()
        and role = 'ADMIN'
    )
  );
