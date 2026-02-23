-- Block 5: HR Review + Feedback loop
-- case_feedback table for HR comments per section

create table if not exists public.case_feedback (
  id uuid primary key default gen_random_uuid(),
  case_id text not null references public.wizard_cases(id) on delete cascade,
  assignment_id text not null references public.case_assignments(id) on delete cascade,
  author_user_id uuid not null,
  author_role text not null check (author_role in ('HR')),
  section text not null check (section in (
    'RELOCATION_BASICS', 'EMPLOYEE_PROFILE', 'FAMILY_MEMBERS', 'ASSIGNMENT_CONTEXT', 'OVERALL'
  )),
  message text not null,
  created_at_ts timestamptz not null default now()
);

create index if not exists case_feedback_case_id_created_idx
  on public.case_feedback (case_id, created_at_ts desc);

create index if not exists case_feedback_assignment_id_created_idx
  on public.case_feedback (assignment_id, created_at_ts desc);

-- RLS
alter table public.case_feedback enable row level security;

-- HR: select/insert only for assignments where hr_user_id = auth.uid()
create policy "hr_select_feedback"
  on public.case_feedback for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.id = case_feedback.assignment_id
        and ca.hr_user_id::uuid = auth.uid()
    )
  );

create policy "hr_insert_feedback"
  on public.case_feedback for insert
  to authenticated
  with check (
    author_user_id = auth.uid()
    and author_role = 'HR'
    and exists (
      select 1 from public.case_assignments ca
      where ca.id = case_feedback.assignment_id
        and ca.hr_user_id::uuid = auth.uid()
    )
  );

-- Employee: select only for assignments where employee_user_id = auth.uid()
create policy "employee_select_feedback"
  on public.case_feedback for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.id = case_feedback.assignment_id
        and ca.employee_user_id::uuid = auth.uid()
    )
  );

grant select, insert on public.case_feedback to authenticated;
