-- HR Command Center: Portfolio & Risk Dashboard
-- Adds risk status, budget, tasks, and case events for HR visibility.

begin;

-- =============================================================================
-- A) Update case_assignments (assignment = HR's primary "case" entity)
--    Add risk_status, budget, expected_start_date
--    Note: Spec mentioned relocation_cases; we use case_assignments for assignment-centric HR flow.
-- =============================================================================
alter table public.case_assignments
  add column if not exists risk_status text check (risk_status in ('green','yellow','red')) default 'green',
  add column if not exists budget_limit numeric,
  add column if not exists budget_estimated numeric,
  add column if not exists expected_start_date date;

create index if not exists idx_case_assignments_risk_status
  on public.case_assignments (risk_status);
create index if not exists idx_case_assignments_expected_start_date
  on public.case_assignments (expected_start_date);

-- Also add to relocation_cases if it exists (spec alignment)
do $$
begin
  if exists (select 1 from information_schema.tables where table_schema='public' and table_name='relocation_cases') then
    if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='relocation_cases' and column_name='risk_status') then
      alter table public.relocation_cases
        add column risk_status text check (risk_status in ('green','yellow','red')) default 'green',
        add column budget_limit numeric,
        add column budget_estimated numeric,
        add column expected_start_date date;
      create index if not exists idx_relocation_cases_risk_status on public.relocation_cases (risk_status);
      create index if not exists idx_relocation_cases_expected_start_date on public.relocation_cases (expected_start_date);
    end if;
  end if;
end $$;

-- =============================================================================
-- B) Create case_events table (Light Audit Log)
-- =============================================================================
create table if not exists public.case_events (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  assignment_id text references public.case_assignments(id) on delete cascade,
  actor_user_id uuid,
  event_type text not null,
  description text,
  created_at timestamptz default now()
);

create index if not exists idx_case_events_case_id on public.case_events (case_id);
create index if not exists idx_case_events_assignment_id on public.case_events (assignment_id);
create index if not exists idx_case_events_created_at on public.case_events (created_at desc);

alter table public.case_events enable row level security;

-- HR can read all events for their cases
drop policy if exists case_events_hr_select on public.case_events;
create policy case_events_hr_select on public.case_events for select to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where (ca.id = case_events.assignment_id or ca.case_id = case_events.case_id)
        and ca.hr_user_id = auth.uid()::text
    )
  );

-- Employees can read events for their own assignment
drop policy if exists case_events_employee_select on public.case_events;
create policy case_events_employee_select on public.case_events for select to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.id = case_events.assignment_id
        and ca.employee_user_id::text = auth.uid()::text
    )
  );

-- HR can insert events for their cases
drop policy if exists case_events_hr_insert on public.case_events;
create policy case_events_hr_insert on public.case_events for insert to authenticated
  with check (
    exists (
      select 1 from public.case_assignments ca
      where (ca.id = case_events.assignment_id or ca.case_id = case_events.case_id)
        and ca.hr_user_id = auth.uid()::text
    )
  );

-- =============================================================================
-- C) Create tasks table if not exists
-- =============================================================================
create table if not exists public.relocation_tasks (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  assignment_id text references public.case_assignments(id) on delete cascade,
  title text not null,
  phase text,
  owner_role text check (owner_role in ('employee','hr')),
  status text check (status in ('todo','in_progress','done','overdue')) default 'todo',
  due_date date,
  created_at timestamptz default now()
);

create index if not exists idx_relocation_tasks_assignment_id on public.relocation_tasks (assignment_id);
create index if not exists idx_relocation_tasks_status on public.relocation_tasks (status);
create index if not exists idx_relocation_tasks_due_date on public.relocation_tasks (due_date);

alter table public.relocation_tasks enable row level security;

drop policy if exists relocation_tasks_hr_select on public.relocation_tasks;
create policy relocation_tasks_hr_select on public.relocation_tasks for select to authenticated
  using (
    exists (select 1 from public.case_assignments ca where ca.id = relocation_tasks.assignment_id and ca.hr_user_id = auth.uid()::text)
  );

drop policy if exists relocation_tasks_employee_select on public.relocation_tasks;
create policy relocation_tasks_employee_select on public.relocation_tasks for select to authenticated
  using (
    exists (select 1 from public.case_assignments ca where ca.id = relocation_tasks.assignment_id and ca.employee_user_id::text = auth.uid()::text)
  );

drop policy if exists relocation_tasks_hr_all on public.relocation_tasks;
create policy relocation_tasks_hr_all on public.relocation_tasks for all to authenticated
  using (
    exists (select 1 from public.case_assignments ca where ca.id = relocation_tasks.assignment_id and ca.hr_user_id = auth.uid()::text)
  )
  with check (
    exists (select 1 from public.case_assignments ca where ca.id = relocation_tasks.assignment_id and ca.hr_user_id = auth.uid()::text)
  );

commit;
