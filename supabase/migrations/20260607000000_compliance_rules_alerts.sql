-- ============================================================================
-- BL-Compliance.1 (AIQ-743) · compliance_rules + compliance_alerts
--
-- Foundation tables for the compliance rule engine.
--   • compliance_rules  — global catalog of rule definitions.
--   • compliance_alerts — a rule firing against a specific case.
--
-- Security (CLAUDE.md hard gates for new public tables):
--   1. ENABLE ROW LEVEL SECURITY on both tables.
--   2. Tenant-scoped policies. compliance_alerts inherits visibility from its
--      parent public.relocation_cases row (admin, or HR scoped to the case's
--      company) — mirroring the live relocation_cases policies. compliance_rules
--      is a non-tenant catalog, readable by any authenticated user (needed to
--      explain why an alert fired); written by service_role.
--   3. REVOKE ALL ... FROM anon (defense-in-depth vs the public anon key).
--
-- relocation_cases (592 rows) is the populated case system the immigration
-- data keys to (immigration_cases.case_id → relocation_cases.id); the newer
-- public.cases is near-empty, so the compliance engine targets relocation_cases.
--
-- Pattern references:
--   20260325000000_case_milestones.sql       (canonical RLS shape)
--   20260601000000_rls_cases_domain.sql       (relocation_cases company scope + is_admin())
--   20260604000000_rce_rule_change_proposals.sql (recent new-table gate)
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- compliance_rules — global rule-definition catalog
-- ----------------------------------------------------------------------------
create table if not exists public.compliance_rules (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  trigger_condition jsonb not null default '{}'::jsonb,
  severity text not null default 'medium'
    check (severity in ('low', 'medium', 'high', 'critical')),
  description text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_compliance_rules_category
  on public.compliance_rules(category);

-- ----------------------------------------------------------------------------
-- compliance_alerts — a rule firing against a specific case
-- ----------------------------------------------------------------------------
create table if not exists public.compliance_alerts (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.relocation_cases(id) on delete cascade,
  rule_id uuid not null references public.compliance_rules(id) on delete restrict,
  status text not null default 'open'
    check (status in ('open', 'resolved', 'dismissed')),
  detail jsonb not null default '{}'::jsonb,
  fired_at timestamptz not null default now(),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_compliance_alerts_case_id
  on public.compliance_alerts(case_id);
create index if not exists idx_compliance_alerts_rule_id
  on public.compliance_alerts(rule_id);
create index if not exists idx_compliance_alerts_open
  on public.compliance_alerts(case_id) where status = 'open';

-- updated_at triggers (standard public.set_updated_at())
drop trigger if exists compliance_rules_set_updated_at on public.compliance_rules;
create trigger compliance_rules_set_updated_at
  before update on public.compliance_rules
  for each row execute function public.set_updated_at();

drop trigger if exists compliance_alerts_set_updated_at on public.compliance_alerts;
create trigger compliance_alerts_set_updated_at
  before update on public.compliance_alerts
  for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------------------
alter table public.compliance_rules enable row level security;
alter table public.compliance_alerts enable row level security;

-- compliance_rules: non-tenant catalog — authenticated read, service_role write.
drop policy if exists compliance_rules_select on public.compliance_rules;
create policy compliance_rules_select on public.compliance_rules
  for select to authenticated using (true);

drop policy if exists compliance_rules_all on public.compliance_rules;
create policy compliance_rules_all on public.compliance_rules
  for all to service_role using (true) with check (true);

-- compliance_alerts: visibility inherits from the parent relocation_case
-- (mirrors the live relocation_cases policies: admin + HR-company scope).
drop policy if exists compliance_alerts_admin_all on public.compliance_alerts;
create policy compliance_alerts_admin_all on public.compliance_alerts
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

drop policy if exists compliance_alerts_select_hr on public.compliance_alerts;
create policy compliance_alerts_select_hr on public.compliance_alerts
  for select to authenticated using (
    exists (
      select 1 from public.relocation_cases rc
      where rc.id = compliance_alerts.case_id
        and rc.company_id = (
          select hr_users.company_id from public.hr_users
          where hr_users.id = (auth.uid())::text
          limit 1
        )
    )
  );

drop policy if exists compliance_alerts_all on public.compliance_alerts;
create policy compliance_alerts_all on public.compliance_alerts
  for all to service_role using (true) with check (true);

-- ----------------------------------------------------------------------------
-- Defense-in-depth: revoke all anon access (SEC-002 hard gate)
-- ----------------------------------------------------------------------------
revoke all on public.compliance_rules from anon;
revoke all on public.compliance_alerts from anon;

commit;

-- ============================================================================
-- Rollback (manual):
--   drop table if exists public.compliance_alerts;
--   drop table if exists public.compliance_rules;
-- ============================================================================
