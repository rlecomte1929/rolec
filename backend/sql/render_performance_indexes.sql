begin;

create index if not exists idx_case_assignments_employee_user_id
  on public.case_assignments (employee_user_id);

create index if not exists idx_case_assignments_employee_identifier
  on public.case_assignments (employee_identifier);

create index if not exists idx_case_assignments_hr_user_id
  on public.case_assignments (hr_user_id);

create index if not exists idx_case_assignments_case_id
  on public.case_assignments (case_id);

commit;
