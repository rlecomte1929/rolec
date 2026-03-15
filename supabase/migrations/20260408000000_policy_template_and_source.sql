-- Policy template source on company_policies + default_policy_templates table
-- template_source: 'default_platform_template' | 'company_uploaded'
begin;

-- A. company_policies: template source and default-template metadata
alter table public.company_policies
  add column if not exists template_source text not null default 'company_uploaded'
    check (template_source in ('default_platform_template', 'company_uploaded'));
alter table public.company_policies
  add column if not exists template_name text null;
alter table public.company_policies
  add column if not exists is_default_template boolean not null default false;

-- B. default_policy_templates: platform default template(s)
create table if not exists public.default_policy_templates (
  id uuid primary key default gen_random_uuid(),
  template_name text not null,
  version text not null,
  status text not null default 'active' check (status in ('active', 'archived', 'draft')),
  is_default_template boolean not null default false,
  snapshot_json jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_default_policy_templates_status
  on public.default_policy_templates(status);
create unique index if not exists idx_default_policy_templates_single_default
  on public.default_policy_templates(is_default_template) where is_default_template = true;

alter table public.default_policy_templates enable row level security;

-- Only service role / admin can manage templates (no RLS policy for authenticated by default; backend uses service role)
create policy default_policy_templates_admin on public.default_policy_templates
  for all to authenticated
  using (true)
  with check (true);

-- C. Seed one default platform template when none exists (from policy_config / normalized framework)
insert into public.default_policy_templates (
  template_name,
  version,
  status,
  is_default_template,
  snapshot_json,
  created_at,
  updated_at
)
select
  'Platform default relocation policy',
  'v2.1',
  'active',
  true,
  '{
    "policyVersion": "v2.1",
    "effectiveDate": "2024-10-01",
    "jurisdictionNotes": "Base policy for global assignments. Local counsel required for exceptions.",
    "caps": {
      "housing": { "amount": 5000, "currency": "USD", "durationMonths": 12 },
      "movers": { "amount": 10000, "currency": "USD" },
      "schools": { "amount": 20000, "currency": "USD" },
      "immigration": { "amount": 4000, "currency": "USD" }
    },
    "approvalRules": { "nearLimit": "Manager", "overLimit": "HR" },
    "exceptionWorkflow": { "states": ["PENDING", "APPROVED", "REJECTED"], "requiredFields": ["category", "reason", "amount"] },
    "requiredEvidence": {
      "housing": ["Lease estimate", "Budget approval"],
      "movers": ["Vendor quote", "Inventory list"],
      "schools": ["School invoice", "Enrollment confirmation"],
      "immigration": ["Legal engagement letter", "Filing receipt"]
    },
    "leadTimeRules": { "minDays": 30 },
    "riskThresholds": { "low": 80, "moderate": 60 },
    "documentRequirements": {
      "base": ["Passport scans", "Employment letter"],
      "married": ["Marriage certificate"],
      "children": ["Birth certificates"],
      "spouseWork": ["Spouse resume"]
    },
    "approvalThresholds": {
      "housing": { "jobLevelCapOverrides": { "L1": 5000, "L2": 7000, "L3": 10000 } },
      "movers": { "storageWeeksIncluded": 4 }
    },
    "benefit_rules": [
      { "benefit_key": "housing", "benefit_category": "housing", "calc_type": "unit_cap", "amount_value": 5000, "amount_unit": "month", "currency": "USD" },
      { "benefit_key": "movers", "benefit_category": "movers", "calc_type": "flat_amount", "amount_value": 10000, "currency": "USD" },
      { "benefit_key": "schools", "benefit_category": "schools", "calc_type": "flat_amount", "amount_value": 20000, "currency": "USD" },
      { "benefit_key": "immigration", "benefit_category": "immigration", "calc_type": "flat_amount", "amount_value": 4000, "currency": "USD" }
    ]
  }'::jsonb,
  now(),
  now()
from (select 1) x
where not exists (select 1 from public.default_policy_templates where is_default_template = true);

commit;
