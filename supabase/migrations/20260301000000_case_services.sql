begin;

create table if not exists public.case_services (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  assignment_id text not null,
  service_key text not null,
  category text not null,
  selected boolean not null default true,
  estimated_cost numeric null,
  currency text null default 'EUR',
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (case_id, service_key)
);

create index if not exists idx_case_services_assignment_id
  on public.case_services (assignment_id);

create index if not exists idx_case_services_case_id
  on public.case_services (case_id);

alter table public.case_services enable row level security;

drop policy if exists "case_services_select" on public.case_services;
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

drop policy if exists "case_services_insert" on public.case_services;
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

drop policy if exists "case_services_update" on public.case_services;
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
