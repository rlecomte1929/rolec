-- SUPERSEDED by 20260403000000_policy_engine_reconciliation.sql
-- (requires resolved_assignment_policies from reconciliation)
begin;
select 1;
/*
create table if not exists public.assignment_policy_service_comparisons (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null,
  case_id text,
  canonical_case_id text,
  resolved_policy_id uuid references public.resolved_assignment_policies(id) on delete cascade,
  service_category text not null,
  requested_value_json jsonb not null default '{}',
  policy_status text not null check (
    policy_status in ('included', 'capped', 'approval_required', 'excluded', 'partial', 'out_of_scope')
  ),
  policy_min_value numeric,
  policy_standard_value numeric,
  policy_max_value numeric,
  currency text,
  amount_unit text,
  variance_json jsonb not null default '{}',
  explanation text,
  evidence_required_json jsonb not null default '[]',
  approval_required boolean not null default false,
  source_rule_ids_json jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_comparisons_assignment on public.assignment_policy_service_comparisons(assignment_id);
create index if not exists idx_comparisons_resolved_policy on public.assignment_policy_service_comparisons(resolved_policy_id);
*/
commit;
