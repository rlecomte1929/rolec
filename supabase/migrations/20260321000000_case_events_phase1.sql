-- Phase 1 Step 1: case_events as immutable event spine
-- Adds payload jsonb and actor_principal_id for canonical event format.
-- RLS: HR/employee read via case_assignments; insert only as self (actor_principal_id = auth.uid()).

begin;

-- Add new columns (keep actor_user_id, description for backward compat)
alter table public.case_events
  add column if not exists payload jsonb not null default '{}',
  add column if not exists actor_principal_id text;

-- Backfill actor_principal_id from actor_user_id
update public.case_events
set actor_principal_id = coalesce(actor_user_id::text, 'system')
where actor_principal_id is null;

-- Set NOT NULL after backfill
alter table public.case_events
  alter column actor_principal_id set default 'system';
alter table public.case_events
  alter column actor_principal_id set not null;

-- Index for list_case_events by case_id (already exists idx_case_events_case_id)
-- Index for created_at desc (already exists idx_case_events_created_at)

-- Replace insert policy: allow insert only when actor_principal_id = current user
drop policy if exists case_events_hr_insert on public.case_events;
create policy case_events_insert_self on public.case_events for insert to authenticated
  with check (actor_principal_id = auth.uid()::text);

commit;
