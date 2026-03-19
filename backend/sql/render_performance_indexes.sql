begin;

create index if not exists idx_case_assignments_employee_user_id
  on public.case_assignments (employee_user_id);

create index if not exists idx_case_assignments_employee_identifier
  on public.case_assignments (employee_identifier);

create index if not exists idx_case_assignments_hr_user_id
  on public.case_assignments (hr_user_id);

create index if not exists idx_case_assignments_case_id
  on public.case_assignments (case_id);

-- Company/profile lookups (get_company_for_user, get_hr_company_id)
create index if not exists idx_profiles_company_id on public.profiles (company_id);
create index if not exists idx_hr_users_profile_id on public.hr_users (profile_id);
create index if not exists idx_relocation_cases_company_id on public.relocation_cases (company_id);

commit;
