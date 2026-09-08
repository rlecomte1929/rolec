begin;

drop policy if exists "case_services_select" on public.case_services;
drop policy if exists "case_services_insert" on public.case_services;
drop policy if exists "case_services_update" on public.case_services;

alter table public.case_services
  alter column assignment_id type text using assignment_id::text,
  alter column case_id type text using case_id::text;

create policy "case_services_select"
  on public.case_services
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.case_assignments ca
      where ca.id = case_services.assignment_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

create policy "case_services_insert"
  on public.case_services
  for insert
  to authenticated
  with check (
    exists (
      select 1
      from public.case_assignments ca
      where ca.id = case_services.assignment_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

create policy "case_services_update"
  on public.case_services
  for update
  to authenticated
  using (
    exists (
      select 1
      from public.case_assignments ca
      where ca.id = case_services.assignment_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1
      from public.case_assignments ca
      where ca.id = case_services.assignment_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

commit;
