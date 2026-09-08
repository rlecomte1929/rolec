-- Operational relocation task tracker: owner, criticality, notes, blocked status
-- Stub CREATE ensures this migration is safe to run before 20260325000000_case_milestones.sql.
-- The full CREATE TABLE IF NOT EXISTS in that migration is a no-op when the table already exists.
begin;

create table if not exists public.case_milestones (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  canonical_case_id text,
  milestone_type text not null,
  title text not null,
  description text,
  target_date date,
  actual_date date,
  status text not null default 'pending'
    check (status in ('pending','in_progress','done','skipped','overdue')),
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.case_milestones
  add column if not exists owner text not null default 'joint';

alter table public.case_milestones
  add column if not exists criticality text not null default 'normal';

alter table public.case_milestones
  add column if not exists notes text;

alter table public.case_milestones
  drop constraint if exists case_milestones_status_check;

alter table public.case_milestones
  add constraint case_milestones_status_check
  check (status in ('pending','in_progress','done','skipped','overdue','blocked'));

commit;
