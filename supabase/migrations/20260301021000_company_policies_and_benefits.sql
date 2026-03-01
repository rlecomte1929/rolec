begin;

create table if not exists public.company_policies (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  title text not null,
  version text null,
  effective_date date null,
  file_url text not null,
  file_type text not null,
  extraction_status text not null default 'pending' check (extraction_status in ('pending','extracted','failed')),
  extracted_at timestamptz null,
  created_by text null,
  created_at timestamptz not null default now()
);

create table if not exists public.policy_benefits (
  id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.company_policies(id) on delete cascade,
  service_category text not null,
  benefit_key text not null,
  benefit_label text not null,
  eligibility jsonb null,
  limits jsonb null,
  notes text null,
  source_quote text null,
  source_section text null,
  confidence numeric null,
  updated_by text null,
  updated_at timestamptz not null default now()
);

create index if not exists idx_policy_benefits_policy_category
  on public.policy_benefits (policy_id, service_category);

create unique index if not exists idx_policy_benefits_policy_key
  on public.policy_benefits (policy_id, benefit_key);

alter table public.company_policies enable row level security;
alter table public.policy_benefits enable row level security;

drop policy if exists company_policies_select on public.company_policies;
create policy company_policies_select on public.company_policies
  for select to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.company_id = company_policies.company_id
    )
  );

drop policy if exists company_policies_write on public.company_policies;
create policy company_policies_write on public.company_policies
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.company_id = company_policies.company_id
        and p.role in ('HR','ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.company_id = company_policies.company_id
        and p.role in ('HR','ADMIN')
    )
  );

drop policy if exists policy_benefits_select on public.policy_benefits;
create policy policy_benefits_select on public.policy_benefits
  for select to authenticated
  using (
    exists (
      select 1 from public.company_policies cp
      join public.profiles p on p.company_id = cp.company_id
      where cp.id = policy_benefits.policy_id
        and p.id = auth.uid()::text
    )
  );

drop policy if exists policy_benefits_write on public.policy_benefits;
create policy policy_benefits_write on public.policy_benefits
  for all to authenticated
  using (
    exists (
      select 1 from public.company_policies cp
      join public.profiles p on p.company_id = cp.company_id
      where cp.id = policy_benefits.policy_id
        and p.id = auth.uid()::text
        and p.role in ('HR','ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.company_policies cp
      join public.profiles p on p.company_id = cp.company_id
      where cp.id = policy_benefits.policy_id
        and p.id = auth.uid()::text
        and p.role in ('HR','ADMIN')
    )
  );

commit;
