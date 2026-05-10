-- SUPERSEDED by 20260403000000_policy_engine_reconciliation.sql
-- (resolved_* tables require policy_versions which is created later in 20260331)
begin;
select 1;
-- Original DDL moved to reconciliation migration
/*
create table if not exists public.resolved_assignment_policies (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null,
  case_id text,
  company_id text not null,
  policy_id uuid not null references public.company_policies(id) on delete cascade,
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  canonical_case_id text,
  resolution_status text not null default 'ok' check (
    resolution_status in ('ok', 'partial', 'review_needed', 'no_policy')
  ),
  resolved_at timestamptz not null default now(),
  resolution_context_json jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(assignment_id)
);
create index if not exists idx_resolved_policies_assignment on public.resolved_assignment_policies(assignment_id);
create index if not exists idx_resolved_policies_case on public.resolved_assignment_policies(case_id);
create index if not exists idx_resolved_policies_company on public.resolved_assignment_policies(company_id);

create table if not exists public.resolved_assignment_policy_benefits (
  id uuid primary key default gen_random_uuid(),
  resolved_policy_id uuid not null references public.resolved_assignment_policies(id) on delete cascade,
  benefit_key text not null,
  included boolean not null default true,
  min_value numeric,
  standard_value numeric,
  max_value numeric,
  currency text,
  amount_unit text,
  frequency text,
  approval_required boolean not null default false,
  evidence_required_json jsonb not null default '[]',
  exclusions_json jsonb not null default '[]',
  condition_summary text,
  source_rule_ids_json jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_resolved_benefits_policy on public.resolved_assignment_policy_benefits(resolved_policy_id);
create index if not exists idx_resolved_benefits_key on public.resolved_assignment_policy_benefits(benefit_key);

create table if not exists public.resolved_assignment_policy_exclusions (
  id uuid primary key default gen_random_uuid(),
  resolved_policy_id uuid not null references public.resolved_assignment_policies(id) on delete cascade,
  benefit_key text,
  domain text not null,
  description text,
  source_rule_ids_json jsonb not null default '[]'
);
create index if not exists idx_resolved_exclusions_policy on public.resolved_assignment_policy_exclusions(resolved_policy_id);
*/
commit;
