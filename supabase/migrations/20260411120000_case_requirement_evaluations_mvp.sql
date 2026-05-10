-- MVP evaluation fields + status vocabulary + deterministic upsert key (system runs)

begin;

alter table public.case_requirement_evaluations
  add column if not exists reason_text text,
  add column if not exists evaluated_at timestamptz,
  add column if not exists evaluated_by text default 'system';

update public.case_requirement_evaluations
set evaluated_by = coalesce(evaluated_by, 'system')
where evaluated_by is null;

update public.case_requirement_evaluations
set evaluated_at = coalesce(evaluated_at, updated_at, created_at)
where evaluated_at is null;

alter table public.case_requirement_evaluations
  alter column evaluated_at set default now();

-- Widen status check: new MVP values plus legacy rows
alter table public.case_requirement_evaluations
  drop constraint if exists case_requirement_evaluations_evaluation_status_check;

alter table public.case_requirement_evaluations
  add constraint case_requirement_evaluations_evaluation_status_check
  check (evaluation_status in (
    'met',
    'missing',
    'not_applicable',
    'needs_review',
    'unknown',
    'pending',
    'unmet',
    'waived'
  ));

commit;
