-- AIQ-756 backfill — rce.roadmap_audit_log
-- Prod-applied out-of-band (schema_migrations version 20260604114840, name
-- "rce_roadmap_audit_log") with no CREATE in the repo. DDL is prod-as-oracle
-- (2026-06-04). Lives in the `rce` schema; FK parents rce.cases /
-- rce.rule_versions / rce.steps are created by 20260528020000_relopass_case_
-- engine_v1.sql, well before this version. Idempotent; no-op on prod.

begin;

create table if not exists rce.roadmap_audit_log (
  roadmap_audit_log_id  uuid        not null default gen_random_uuid(),
  case_id               uuid        not null,
  step_id               uuid,
  rule_version_id       uuid        not null,
  source_url            text,
  source_fetch_date     date,
  generated_by          text        not null,
  generated_at          timestamptz not null default now(),
  confidence_at_time    numeric,
  specialist_corrections jsonb,
  created_at            timestamptz not null default now(),
  constraint roadmap_audit_log_pkey primary key (roadmap_audit_log_id),
  constraint roadmap_audit_log_case_id_fkey
    foreign key (case_id) references rce.cases (case_id) on delete cascade,
  constraint roadmap_audit_log_rule_version_id_fkey
    foreign key (rule_version_id) references rce.rule_versions (rule_version_id) on delete restrict,
  constraint roadmap_audit_log_step_id_fkey
    foreign key (step_id) references rce.steps (step_id) on delete set null,
  constraint roadmap_audit_log_generated_by_check
    check (generated_by = any (array['AI'::text, 'SPECIALIST'::text]))
);

create index if not exists roadmap_audit_log_by_case
  on rce.roadmap_audit_log (case_id, generated_at desc);
create index if not exists roadmap_audit_log_by_version
  on rce.roadmap_audit_log (rule_version_id);

alter table rce.roadmap_audit_log enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname='rce'
      and tablename='roadmap_audit_log' and policyname='roadmap_audit_log_case_visibility_read') then
    create policy roadmap_audit_log_case_visibility_read on rce.roadmap_audit_log
      for select to public using (
        exists (select 1 from rce.cases c where c.case_id = roadmap_audit_log.case_id));
  end if;
  if not exists (select 1 from pg_policies where schemaname='rce'
      and tablename='roadmap_audit_log' and policyname='roadmap_audit_log_case_visibility_insert') then
    create policy roadmap_audit_log_case_visibility_insert on rce.roadmap_audit_log
      for insert to public with check (
        exists (select 1 from rce.cases c where c.case_id = roadmap_audit_log.case_id));
  end if;
  if not exists (select 1 from pg_policies where schemaname='rce'
      and tablename='roadmap_audit_log' and policyname='roadmap_audit_log_service_role_all') then
    create policy roadmap_audit_log_service_role_all on rce.roadmap_audit_log
      for all to public using (auth.role() = 'service_role'::text)
      with check (auth.role() = 'service_role'::text);
  end if;
end $$;

revoke all on rce.roadmap_audit_log from anon;

commit;
