-- Compensation & Allowance: structured policy config (manual entry foundation).
-- Separate from company_policies / policy_versions (document pipeline). Designed so future
-- HR policy uploads can hydrate rows into policy_config_benefits.
-- Idempotent DDL + partial unique indexes: safe to re-apply; RLS policies require this file on Supabase
-- (local SQLite fallback in database.py does not replicate RLS).
begin;

-- One logical config per company + config_key (e.g. compensation_allowance).
create table if not exists public.policy_configs (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  name text not null default 'Compensation & Allowance',
  config_key text not null default 'compensation_allowance',
  description text,
  is_active boolean not null default true,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, config_key)
);

create index if not exists idx_policy_configs_company on public.policy_configs (company_id);
create index if not exists idx_policy_configs_active on public.policy_configs (company_id, is_active)
  where is_active = true;

-- Version lifecycle: draft → (optional approved) → published; previous published → archived.
create table if not exists public.policy_config_versions (
  id uuid primary key default gen_random_uuid(),
  policy_config_id uuid not null references public.policy_configs (id) on delete cascade,
  version_number int not null,
  status text not null default 'draft' check (
    status in ('draft', 'approved', 'published', 'archived')
  ),
  effective_date date not null,
  published_at timestamptz,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (policy_config_id, version_number)
);

create index if not exists idx_pc_versions_config on public.policy_config_versions (policy_config_id);
create index if not exists idx_pc_versions_status on public.policy_config_versions (policy_config_id, status);
create index if not exists idx_pc_versions_effective on public.policy_config_versions (effective_date);

-- At most one published row per policy_config (active published matrix).
create unique index if not exists uq_policy_config_one_published
  on public.policy_config_versions (policy_config_id)
  where status = 'published';

-- At most one draft per policy_config (simplifies HR UX; clone replaces draft if needed in app).
create unique index if not exists uq_policy_config_one_draft
  on public.policy_config_versions (policy_config_id)
  where status = 'draft';

create table if not exists public.policy_config_benefits (
  id uuid primary key default gen_random_uuid(),
  policy_config_version_id uuid not null references public.policy_config_versions (id) on delete cascade,
  benefit_key text not null,
  benefit_label text not null,
  category text not null check (
    category in (
      'pre_assignment_support',
      'relocation_assistance',
      'compensation_allowances',
      'family_support_education',
      'leave_repatriation',
      'tax_payroll'
    )
  ),
  covered boolean not null default false,
  value_type text not null default 'none' check (
    value_type in ('currency', 'percentage', 'text', 'none')
  ),
  amount_value numeric,
  currency_code text,
  percentage_value numeric,
  unit_frequency text not null default 'one_time' check (
    unit_frequency in (
      'one_time', 'monthly', 'yearly', 'per_trip', 'per_day', 'per_dependent', 'custom'
    )
  ),
  cap_rule_json jsonb not null default '{}',
  notes text,
  conditions_json jsonb not null default '{}',
  assignment_types jsonb not null default '[]',
  family_statuses jsonb not null default '[]',
  targeting_signature text not null default 'global',
  is_active boolean not null default true,
  display_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (policy_config_version_id, benefit_key, targeting_signature)
);

create index if not exists idx_pc_benefits_version on public.policy_config_benefits (policy_config_version_id);
create index if not exists idx_pc_benefits_key on public.policy_config_benefits (benefit_key);
create index if not exists idx_pc_benefits_category on public.policy_config_benefits (policy_config_version_id, category);

alter table public.policy_configs enable row level security;
alter table public.policy_config_versions enable row level security;
alter table public.policy_config_benefits enable row level security;

-- HR: same company; Admin: any (matches policy_versions pattern).
create policy policy_configs_rw on public.policy_configs
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and (
          p.role = 'ADMIN'
          or (p.role = 'HR' and p.company_id = policy_configs.company_id)
        )
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and (
          p.role = 'ADMIN'
          or (p.role = 'HR' and p.company_id = policy_configs.company_id)
        )
    )
  );

create policy policy_config_versions_rw on public.policy_config_versions
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_configs c
      where c.id = policy_config_versions.policy_config_id
        and exists (
          select 1 from public.profiles p
          where p.id = auth.uid()::text
            and (
              p.role = 'ADMIN'
              or (p.role = 'HR' and p.company_id = c.company_id)
            )
        )
    )
  )
  with check (
    exists (
      select 1 from public.policy_configs c
      where c.id = policy_config_versions.policy_config_id
        and exists (
          select 1 from public.profiles p
          where p.id = auth.uid()::text
            and (
              p.role = 'ADMIN'
              or (p.role = 'HR' and p.company_id = c.company_id)
            )
        )
    )
  );

create policy policy_config_benefits_rw on public.policy_config_benefits
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_config_versions v
      join public.policy_configs c on c.id = v.policy_config_id
      where v.id = policy_config_benefits.policy_config_version_id
        and exists (
          select 1 from public.profiles p
          where p.id = auth.uid()::text
            and (
              p.role = 'ADMIN'
              or (p.role = 'HR' and p.company_id = c.company_id)
            )
        )
    )
  )
  with check (
    exists (
      select 1 from public.policy_config_versions v
      join public.policy_configs c on c.id = v.policy_config_id
      where v.id = policy_config_benefits.policy_config_version_id
        and exists (
          select 1 from public.profiles p
          where p.id = auth.uid()::text
            and (
              p.role = 'ADMIN'
              or (p.role = 'HR' and p.company_id = c.company_id)
            )
        )
    )
  );

-- Service role / backend full access
create policy policy_configs_service on public.policy_configs
  for all to service_role using (true) with check (true);
create policy policy_config_versions_service on public.policy_config_versions
  for all to service_role using (true) with check (true);
create policy policy_config_benefits_service on public.policy_config_benefits
  for all to service_role using (true) with check (true);

-- Employees: read-only access to published matrix for their company (direct Supabase / PostgREST).
create policy policy_configs_employee_read on public.policy_configs
  for select to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.role = 'EMPLOYEE'
        and p.company_id = policy_configs.company_id
    )
  );

create policy policy_config_versions_employee_read on public.policy_config_versions
  for select to authenticated
  using (
    status = 'published'
    and exists (
      select 1 from public.policy_configs c
      where c.id = policy_config_versions.policy_config_id
        and exists (
          select 1 from public.profiles p
          where p.id = auth.uid()::text
            and p.role = 'EMPLOYEE'
            and p.company_id = c.company_id
        )
    )
  );

create policy policy_config_benefits_employee_read on public.policy_config_benefits
  for select to authenticated
  using (
    exists (
      select 1 from public.policy_config_versions v
      join public.policy_configs c on c.id = v.policy_config_id
      where v.id = policy_config_benefits.policy_config_version_id
        and v.status = 'published'
        and exists (
          select 1 from public.profiles p
          where p.id = auth.uid()::text
            and p.role = 'EMPLOYEE'
            and p.company_id = c.company_id
        )
    )
  );

commit;
