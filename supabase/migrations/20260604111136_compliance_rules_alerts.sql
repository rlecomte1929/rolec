-- AIQ-756 backfill — public.compliance_rules + public.compliance_alerts
-- Prod-applied out-of-band (schema_migrations version 20260604111136, name
-- "compliance_rules_alerts") with no CREATE in the repo. DDL is prod-as-oracle
-- (2026-06-04). compliance_rules is created first because compliance_alerts
-- FKs into it. FK parent relocation_cases is from the Feb-21 baseline.
-- Idempotent (IF NOT EXISTS + pg_policies guards); no-op on prod.
--
-- NOTE: the later prod migration "compliance_alerts_target_relocation_cases"
-- (20260604113038) is reconciled by an empty stub in this PR — the FK to
-- relocation_cases is already part of compliance_alerts' create below, so the
-- separate retarget ALTER is redundant on a fresh replay.

begin;

create table if not exists public.compliance_rules (
  id                uuid        not null default gen_random_uuid(),
  category          text        not null,
  trigger_condition jsonb       not null default '{}'::jsonb,
  severity          text        not null default 'medium'::text,
  description       text,
  active            boolean     not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint compliance_rules_pkey primary key (id),
  constraint compliance_rules_severity_check
    check (severity = any (array['low'::text, 'medium'::text, 'high'::text, 'critical'::text]))
);

create index if not exists idx_compliance_rules_category
  on public.compliance_rules (category);

create table if not exists public.compliance_alerts (
  id          uuid        not null default gen_random_uuid(),
  case_id     uuid        not null,
  rule_id     uuid        not null,
  status      text        not null default 'open'::text,
  detail      jsonb       not null default '{}'::jsonb,
  fired_at    timestamptz not null default now(),
  resolved_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint compliance_alerts_pkey primary key (id),
  constraint compliance_alerts_case_id_fkey
    foreign key (case_id) references public.relocation_cases (id) on delete cascade,
  constraint compliance_alerts_rule_id_fkey
    foreign key (rule_id) references public.compliance_rules (id) on delete restrict,
  constraint compliance_alerts_status_check
    check (status = any (array['open'::text, 'resolved'::text, 'dismissed'::text]))
);

create index if not exists idx_compliance_alerts_case_id
  on public.compliance_alerts (case_id);
create index if not exists idx_compliance_alerts_open
  on public.compliance_alerts (case_id) where (status = 'open'::text);
create index if not exists idx_compliance_alerts_rule_id
  on public.compliance_alerts (rule_id);

alter table public.compliance_rules  enable row level security;
alter table public.compliance_alerts enable row level security;

do $$
begin
  -- compliance_rules: global catalog — authenticated read, service-role write.
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='compliance_rules' and policyname='compliance_rules_select') then
    create policy compliance_rules_select on public.compliance_rules
      for select to authenticated using (true);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='compliance_rules' and policyname='compliance_rules_all') then
    create policy compliance_rules_all on public.compliance_rules
      for all to service_role using (true) with check (true);
  end if;

  -- compliance_alerts: HR of the owning company reads; admin all; service all.
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='compliance_alerts' and policyname='compliance_alerts_select_hr') then
    create policy compliance_alerts_select_hr on public.compliance_alerts
      for select to authenticated using (
        exists (
          select 1 from public.relocation_cases rc
          where rc.id = compliance_alerts.case_id
            and rc.company_id = (
              select hr_users.company_id from public.hr_users
              where hr_users.id = (auth.uid())::text limit 1)
        )
      );
  end if;
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='compliance_alerts' and policyname='compliance_alerts_admin_all') then
    create policy compliance_alerts_admin_all on public.compliance_alerts
      for all to authenticated using (is_admin()) with check (is_admin());
  end if;
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='compliance_alerts' and policyname='compliance_alerts_all') then
    create policy compliance_alerts_all on public.compliance_alerts
      for all to service_role using (true) with check (true);
  end if;
end $$;

revoke all on public.compliance_rules  from anon;
revoke all on public.compliance_alerts from anon;

commit;
