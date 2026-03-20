-- Operational relocation task tracker: owner, criticality, notes, blocked status
begin;

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
