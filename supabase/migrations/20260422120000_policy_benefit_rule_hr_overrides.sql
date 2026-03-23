-- HR override layer: adjusts effective entitlements without mutating extraction / normalized draft artifacts.
-- One current row per (policy_version_id, benefit_rule_id); changes append to audit log.

begin;

create table if not exists public.policy_benefit_rule_hr_overrides (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions (id) on delete cascade,
  benefit_rule_id uuid not null references public.policy_benefit_rules (id) on delete cascade,
  service_visibility text null
    check (service_visibility is null or service_visibility in ('default', 'force_included', 'force_excluded')),
  amount_value_override numeric null,
  amount_unit_override text null,
  currency_override text null,
  duration_quantity_json jsonb null,
  approval_required_override boolean null,
  hr_notes text null,
  created_by text null,
  updated_by text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (policy_version_id, benefit_rule_id)
);

create index if not exists idx_pbr_hr_overrides_version
  on public.policy_benefit_rule_hr_overrides (policy_version_id);
create index if not exists idx_pbr_hr_overrides_rule
  on public.policy_benefit_rule_hr_overrides (benefit_rule_id);

create table if not exists public.policy_benefit_rule_hr_override_audit (
  id uuid primary key default gen_random_uuid(),
  override_id uuid not null references public.policy_benefit_rule_hr_overrides (id) on delete cascade,
  action text not null check (action in ('insert', 'update', 'delete')),
  previous_json jsonb null,
  new_json jsonb null,
  actor_id text null,
  created_at timestamptz not null default now()
);

create index if not exists idx_pbr_hr_override_audit_override
  on public.policy_benefit_rule_hr_override_audit (override_id, created_at desc);

alter table public.policy_benefit_rule_hr_overrides enable row level security;
alter table public.policy_benefit_rule_hr_override_audit enable row level security;

drop policy if exists policy_benefit_rule_hr_overrides_company on public.policy_benefit_rule_hr_overrides;
create policy policy_benefit_rule_hr_overrides_company on public.policy_benefit_rule_hr_overrides
  for all to authenticated
  using (exists (
    select 1 from public.policy_versions pv
    join public.company_policies cp on cp.id = pv.policy_id
    join public.profiles p on p.company_id = cp.company_id
    where pv.id = policy_benefit_rule_hr_overrides.policy_version_id
      and (p.id = auth.uid()::text or p.role = 'ADMIN')
  ))
  with check (exists (
    select 1 from public.policy_versions pv
    join public.company_policies cp on cp.id = pv.policy_id
    join public.profiles p on p.company_id = cp.company_id
    where pv.id = policy_benefit_rule_hr_overrides.policy_version_id
      and (p.id = auth.uid()::text or p.role = 'ADMIN')
  ));

drop policy if exists policy_benefit_rule_hr_override_audit_company on public.policy_benefit_rule_hr_override_audit;
create policy policy_benefit_rule_hr_override_audit_company on public.policy_benefit_rule_hr_override_audit
  for all to authenticated
  using (exists (
    select 1 from public.policy_benefit_rule_hr_overrides o
    join public.policy_versions pv on pv.id = o.policy_version_id
    join public.company_policies cp on cp.id = pv.policy_id
    join public.profiles p on p.company_id = cp.company_id
    where o.id = policy_benefit_rule_hr_override_audit.override_id
      and (p.id = auth.uid()::text or p.role = 'ADMIN')
  ))
  with check (exists (
    select 1 from public.policy_benefit_rule_hr_overrides o
    join public.policy_versions pv on pv.id = o.policy_version_id
    join public.company_policies cp on cp.id = pv.policy_id
    join public.profiles p on p.company_id = cp.company_id
    where o.id = policy_benefit_rule_hr_override_audit.override_id
      and (p.id = auth.uid()::text or p.role = 'ADMIN')
  ));

commit;
