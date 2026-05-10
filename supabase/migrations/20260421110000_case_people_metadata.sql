-- Optional person attributes for graph context (no document/eval changes)

begin;

alter table public.case_people
  add column if not exists metadata jsonb not null default '{}'::jsonb;

comment on column public.case_people.metadata is
  'Snapshot of employee-facing fields synced from live assignment data (e.g. employee_profiles JSON).';

-- At most one graph row with role employee per mobility case (idempotent sync target)
create unique index if not exists case_people_one_employee_per_case
  on public.case_people (case_id)
  where role = 'employee';

commit;
