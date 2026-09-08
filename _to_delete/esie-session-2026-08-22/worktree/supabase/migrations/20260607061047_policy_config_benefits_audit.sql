-- AIQ-839 (W5): field-level audit trail for the policy_config_benefits manual-override
-- (PUT /policy-config/draft) path. Mirrors policy_benefit_rule_hr_override_audit.
--
-- New table in public schema => RLS hard gate (CLAUDE.md): enable RLS + ≥1 policy + revoke anon.
--
-- benefit_id has NO foreign key on purpose: the PUT draft path deletes and re-inserts
-- every benefit row on each save, so a cascading FK would wipe the audit history we are
-- trying to keep. policy_config_version_id is denormalized so the company-scoped RLS
-- check survives the benefit-row churn.

begin;

create table if not exists public.policy_config_benefits_audit (
  id uuid primary key default gen_random_uuid(),
  benefit_id uuid null,
  policy_config_version_id uuid null,
  benefit_key text null,
  action text not null check (action in ('insert', 'update', 'delete')),
  old_value jsonb null,
  new_value jsonb null,
  source text null,
  changed_by text null,
  changed_at timestamptz not null default now()
);

create index if not exists idx_pcb_audit_benefit
  on public.policy_config_benefits_audit (benefit_id, changed_at desc);
create index if not exists idx_pcb_audit_version
  on public.policy_config_benefits_audit (policy_config_version_id, changed_at desc);

alter table public.policy_config_benefits_audit enable row level security;

drop policy if exists policy_config_benefits_audit_hr_all on public.policy_config_benefits_audit;
create policy policy_config_benefits_audit_hr_all on public.policy_config_benefits_audit
  for all to authenticated
  using (
    (policy_config_version_id is not null
      and public.policy_config_version_in_company_scope(policy_config_version_id))
    or public.is_admin()
  )
  with check (
    (policy_config_version_id is not null
      and public.policy_config_version_in_company_scope(policy_config_version_id))
    or public.is_admin()
  );

drop policy if exists policy_config_benefits_audit_service on public.policy_config_benefits_audit;
create policy policy_config_benefits_audit_service on public.policy_config_benefits_audit
  for all to service_role using (true) with check (true);

revoke all on public.policy_config_benefits_audit from anon;

commit;
