-- ============================================================================
-- SEC-RLSb · RLS for the Policy / HR domain  (AIQ-659, audit stage-1)
-- ============================================================================
-- Closes the policy-less exposure (SEC-002 class) for HR-owned policy tables.
-- The Supabase `anon` key ships in the frontend bundle and PostgREST exposes the
-- `public` schema, so any table without RLS is world-readable. This migration
-- enables RLS + scoping policies on every HR/policy table triaged into SEC-RLSb
-- and removes them from supabase/rls_allowlist.txt.
--
-- Identity model (verified against live schema 2026-05-30):
--   * hr_users.profile_id  = auth.uid()::text
--   * hr_users.company_id  = company UUID rendered as text, the SAME value stored
--     in policy_documents.company_id / company_policies.company_id / etc.
--   * Employees have no hr_users row -> they see nothing on company-scoped tables.
--   * public.is_admin() (no args, already in the DB) gives the admin CMS a carve-out.
--
-- Policy shapes used below:
--   A. Company-scoped HR  -> SELECT+write for HR of the owning company (or admin),
--      either directly on company_id or via an EXISTS join to the owning parent.
--   B. Shared knowledge    -> SELECT for any authenticated user; writes admin-only
--      (canonical_policy_* knowledge graph + the global policy_rules catalog).
--   C. Server-internal     -> service_role only, no authenticated access
--      (policy_extraction_locks = extraction pipeline lock table; hr_policies =
--       legacy table keyed by a free-text company_entity that cannot be mapped to
--       a company UUID, so it is locked to the backend service role — the HR
--       command center reads it through the FastAPI/direct-DB path, not anon).
--
-- Every table additionally gets an explicit service_role ALL policy (mirrors the
-- canonical case_milestones pattern) and `REVOKE ALL ... FROM anon`.
--
-- Rollback block is at the very bottom of this file.
-- ============================================================================

begin;

-- ──────────────────────────────────────────────────────────────────────────
-- Helper functions (SECURITY DEFINER so they can read hr_users regardless of
-- that table's own RLS; STABLE so PostgreSQL hoists them out of row loops).
-- ──────────────────────────────────────────────────────────────────────────

-- Company IDs (as text) the current authenticated user is an HR member of.
create or replace function public.hr_company_ids()
returns setof text
language sql
stable
security definer
set search_path = public
as $$
  select company_id
  from public.hr_users
  where profile_id = (select auth.uid())::text
$$;

-- A policy_version row is in the caller's company scope if its parent
-- company_policies row (policy_id) OR its source policy_documents row
-- (source_policy_document_id) belongs to one of the caller's companies.
create or replace function public.policy_version_in_company_scope(pv_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.policy_versions pv
    where pv.id = pv_id
      and (
        exists (
          select 1 from public.company_policies cp
          where cp.id = pv.policy_id
            and cp.company_id in (select public.hr_company_ids())
        )
        or exists (
          select 1 from public.policy_documents d
          where d.id = pv.source_policy_document_id
            and d.company_id in (select public.hr_company_ids())
        )
      )
  )
$$;

-- A policy_config_version row is in scope if its policy_configs parent
-- (policy_config_id -> policy_configs.company_id) belongs to the caller.
create or replace function public.policy_config_version_in_company_scope(cv_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.policy_config_versions cv
    join public.policy_configs pc on pc.id = cv.policy_config_id
    where cv.id = cv_id
      and pc.company_id in (select public.hr_company_ids())
  )
$$;

revoke all on function public.hr_company_ids() from public;
revoke all on function public.policy_version_in_company_scope(uuid) from public;
revoke all on function public.policy_config_version_in_company_scope(uuid) from public;
grant execute on function public.hr_company_ids() to authenticated, service_role;
grant execute on function public.policy_version_in_company_scope(uuid) to authenticated, service_role;
grant execute on function public.policy_config_version_in_company_scope(uuid) to authenticated, service_role;

-- ──────────────────────────────────────────────────────────────────────────
-- GROUP A.1 — direct company_id (text), company-scoped HR read+write
-- ──────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  tables text[] := array[
    'company_policies',
    'company_preferred_suppliers',
    'company_policy_assistant_bindings',
    'policy_assistant_answer_audits',
    'policy_configs',
    'policy_documents',
    'policy_knowledge_snapshots'
  ];
begin
  foreach t in array tables loop
    execute format('alter table public.%I enable row level security;', t);
    execute format('drop policy if exists %I on public.%I;', t || '_hr_all', t);
    execute format($f$
      create policy %I on public.%I
        for all to authenticated
        using (company_id in (select public.hr_company_ids()) or public.is_admin())
        with check (company_id in (select public.hr_company_ids()) or public.is_admin());
    $f$, t || '_hr_all', t);
    execute format('drop policy if exists %I on public.%I;', t || '_service', t);
    execute format($f$
      create policy %I on public.%I for all to service_role using (true) with check (true);
    $f$, t || '_service', t);
    execute format('revoke all on public.%I from anon;', t);
  end loop;
end $$;

-- GROUP A.1b — company_vendor_selections: company_id is uuid, cast to text.
alter table public.company_vendor_selections enable row level security;
drop policy if exists company_vendor_selections_hr_all on public.company_vendor_selections;
create policy company_vendor_selections_hr_all on public.company_vendor_selections
  for all to authenticated
  using (company_id::text in (select public.hr_company_ids()) or public.is_admin())
  with check (company_id::text in (select public.hr_company_ids()) or public.is_admin());
drop policy if exists company_vendor_selections_service on public.company_vendor_selections;
create policy company_vendor_selections_service on public.company_vendor_selections
  for all to service_role using (true) with check (true);
revoke all on public.company_vendor_selections from anon;

-- ──────────────────────────────────────────────────────────────────────────
-- GROUP A.2 — children of policy_documents (policy_document_id -> company_id)
-- ──────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  tables text[] := array[
    'policy_document_chunks',
    'policy_document_clauses',
    'policy_processing_runs'
  ];
begin
  foreach t in array tables loop
    execute format('alter table public.%I enable row level security;', t);
    execute format('drop policy if exists %I on public.%I;', t || '_hr_all', t);
    execute format($f$
      create policy %I on public.%I
        for all to authenticated
        using (
          exists (
            select 1 from public.policy_documents d
            where d.id = %I.policy_document_id
              and d.company_id in (select public.hr_company_ids())
          ) or public.is_admin()
        )
        with check (
          exists (
            select 1 from public.policy_documents d
            where d.id = %I.policy_document_id
              and d.company_id in (select public.hr_company_ids())
          ) or public.is_admin()
        );
    $f$, t || '_hr_all', t, t, t);
    execute format('drop policy if exists %I on public.%I;', t || '_service', t);
    execute format($f$
      create policy %I on public.%I for all to service_role using (true) with check (true);
    $f$, t || '_service', t);
    execute format('revoke all on public.%I from anon;', t);
  end loop;
end $$;

-- GROUP A.3 — policy_facts: snapshot_id -> policy_knowledge_snapshots.company_id
alter table public.policy_facts enable row level security;
drop policy if exists policy_facts_hr_all on public.policy_facts;
create policy policy_facts_hr_all on public.policy_facts
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_knowledge_snapshots s
      where s.id = policy_facts.snapshot_id
        and s.company_id in (select public.hr_company_ids())
    ) or public.is_admin()
  )
  with check (
    exists (
      select 1 from public.policy_knowledge_snapshots s
      where s.id = policy_facts.snapshot_id
        and s.company_id in (select public.hr_company_ids())
    ) or public.is_admin()
  );
drop policy if exists policy_facts_service on public.policy_facts;
create policy policy_facts_service on public.policy_facts for all to service_role using (true) with check (true);
revoke all on public.policy_facts from anon;

-- GROUP A.4 — policy_versions: policy_id -> company_policies / source doc fallback
alter table public.policy_versions enable row level security;
drop policy if exists policy_versions_hr_all on public.policy_versions;
create policy policy_versions_hr_all on public.policy_versions
  for all to authenticated
  using (public.policy_version_in_company_scope(id) or public.is_admin())
  with check (public.policy_version_in_company_scope(id) or public.is_admin());
drop policy if exists policy_versions_service on public.policy_versions;
create policy policy_versions_service on public.policy_versions for all to service_role using (true) with check (true);
revoke all on public.policy_versions from anon;

-- GROUP A.5 — children of policy_versions (policy_version_id)
do $$
declare
  t text;
  tables text[] := array[
    'policy_assignment_type_applicability',
    'policy_benefit_rules',
    'policy_benefit_rule_hr_overrides',
    'policy_evidence_requirements',
    'policy_exclusions',
    'policy_family_status_applicability',
    'policy_rule_conditions',
    'policy_source_links',
    'policy_tier_overrides'
  ];
begin
  foreach t in array tables loop
    execute format('alter table public.%I enable row level security;', t);
    execute format('drop policy if exists %I on public.%I;', t || '_hr_all', t);
    execute format($f$
      create policy %I on public.%I
        for all to authenticated
        using (public.policy_version_in_company_scope(%I.policy_version_id) or public.is_admin())
        with check (public.policy_version_in_company_scope(%I.policy_version_id) or public.is_admin());
    $f$, t || '_hr_all', t, t, t);
    execute format('drop policy if exists %I on public.%I;', t || '_service', t);
    execute format($f$
      create policy %I on public.%I for all to service_role using (true) with check (true);
    $f$, t || '_service', t);
    execute format('revoke all on public.%I from anon;', t);
  end loop;
end $$;

-- GROUP A.6 — policy_configs chain (policy_config_versions, policy_config_benefits)
alter table public.policy_config_versions enable row level security;
drop policy if exists policy_config_versions_hr_all on public.policy_config_versions;
create policy policy_config_versions_hr_all on public.policy_config_versions
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_configs pc
      where pc.id = policy_config_versions.policy_config_id
        and pc.company_id in (select public.hr_company_ids())
    ) or public.is_admin()
  )
  with check (
    exists (
      select 1 from public.policy_configs pc
      where pc.id = policy_config_versions.policy_config_id
        and pc.company_id in (select public.hr_company_ids())
    ) or public.is_admin()
  );
drop policy if exists policy_config_versions_service on public.policy_config_versions;
create policy policy_config_versions_service on public.policy_config_versions for all to service_role using (true) with check (true);
revoke all on public.policy_config_versions from anon;

-- policy_config_benefits: policy_config_version_id -> policy_config_versions -> policy_configs
alter table public.policy_config_benefits enable row level security;
drop policy if exists policy_config_benefits_hr_all on public.policy_config_benefits;
create policy policy_config_benefits_hr_all on public.policy_config_benefits
  for all to authenticated
  using (public.policy_config_version_in_company_scope(policy_config_version_id) or public.is_admin())
  with check (public.policy_config_version_in_company_scope(policy_config_version_id) or public.is_admin());
drop policy if exists policy_config_benefits_service on public.policy_config_benefits;
create policy policy_config_benefits_service on public.policy_config_benefits for all to service_role using (true) with check (true);
revoke all on public.policy_config_benefits from anon;

-- policy_benefit_jurisdiction_overrides: benefit_row_id -> policy_config_benefits -> ...
alter table public.policy_benefit_jurisdiction_overrides enable row level security;
drop policy if exists policy_benefit_jurisdiction_overrides_hr_all on public.policy_benefit_jurisdiction_overrides;
create policy policy_benefit_jurisdiction_overrides_hr_all on public.policy_benefit_jurisdiction_overrides
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_config_benefits b
      where b.id = policy_benefit_jurisdiction_overrides.benefit_row_id
        and public.policy_config_version_in_company_scope(b.policy_config_version_id)
    ) or public.is_admin()
  )
  with check (
    exists (
      select 1 from public.policy_config_benefits b
      where b.id = policy_benefit_jurisdiction_overrides.benefit_row_id
        and public.policy_config_version_in_company_scope(b.policy_config_version_id)
    ) or public.is_admin()
  );
drop policy if exists policy_benefit_jurisdiction_overrides_service on public.policy_benefit_jurisdiction_overrides;
create policy policy_benefit_jurisdiction_overrides_service on public.policy_benefit_jurisdiction_overrides for all to service_role using (true) with check (true);
revoke all on public.policy_benefit_jurisdiction_overrides from anon;

-- policy_benefit_rule_hr_override_audit: override_id -> policy_benefit_rule_hr_overrides.policy_version_id
alter table public.policy_benefit_rule_hr_override_audit enable row level security;
drop policy if exists policy_benefit_rule_hr_override_audit_hr_all on public.policy_benefit_rule_hr_override_audit;
create policy policy_benefit_rule_hr_override_audit_hr_all on public.policy_benefit_rule_hr_override_audit
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_benefit_rule_hr_overrides o
      where o.id = policy_benefit_rule_hr_override_audit.override_id
        and public.policy_version_in_company_scope(o.policy_version_id)
    ) or public.is_admin()
  )
  with check (
    exists (
      select 1 from public.policy_benefit_rule_hr_overrides o
      where o.id = policy_benefit_rule_hr_override_audit.override_id
        and public.policy_version_in_company_scope(o.policy_version_id)
    ) or public.is_admin()
  );
drop policy if exists policy_benefit_rule_hr_override_audit_service on public.policy_benefit_rule_hr_override_audit;
create policy policy_benefit_rule_hr_override_audit_service on public.policy_benefit_rule_hr_override_audit for all to service_role using (true) with check (true);
revoke all on public.policy_benefit_rule_hr_override_audit from anon;

-- ──────────────────────────────────────────────────────────────────────────
-- GROUP A.7 — compliance_*: assignment_id -> case_assignments -> hr_users.company_id
-- (HR of the company that owns the assignment, or the assigned HR directly)
-- ──────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  tables text[] := array['compliance_actions', 'compliance_reports'];
begin
  foreach t in array tables loop
    execute format('alter table public.%I enable row level security;', t);
    execute format('drop policy if exists %I on public.%I;', t || '_hr_all', t);
    execute format($f$
      create policy %I on public.%I
        for all to authenticated
        using (
          exists (
            select 1 from public.case_assignments ca
            where ca.id = %I.assignment_id
              and (
                ca.hr_user_id = (select auth.uid())::text
                or exists (
                  select 1 from public.hr_users hu
                  where hu.profile_id = ca.hr_user_id
                    and hu.company_id in (select public.hr_company_ids())
                )
              )
          ) or public.is_admin()
        )
        with check (
          exists (
            select 1 from public.case_assignments ca
            where ca.id = %I.assignment_id
              and (
                ca.hr_user_id = (select auth.uid())::text
                or exists (
                  select 1 from public.hr_users hu
                  where hu.profile_id = ca.hr_user_id
                    and hu.company_id in (select public.hr_company_ids())
                )
              )
          ) or public.is_admin()
        );
    $f$, t || '_hr_all', t, t, t);
    execute format('drop policy if exists %I on public.%I;', t || '_service', t);
    execute format($f$
      create policy %I on public.%I for all to service_role using (true) with check (true);
    $f$, t || '_service', t);
    execute format('revoke all on public.%I from anon;', t);
  end loop;
end $$;

-- ──────────────────────────────────────────────────────────────────────────
-- GROUP B — shared knowledge graph: authenticated SELECT, admin-only writes.
-- canonical_policy_* is a cross-company knowledge graph (NOT per-company) and
-- policy_rules is a global rule catalog (no company column at all).
-- ──────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  tables text[] := array[
    'canonical_policy_documents',
    'canonical_policy_document_chunks',
    'canonical_policy_facts',
    'canonical_policy_fact_validation_errors',
    'policy_rules'
  ];
begin
  foreach t in array tables loop
    execute format('alter table public.%I enable row level security;', t);
    execute format('drop policy if exists %I on public.%I;', t || '_auth_read', t);
    execute format($f$
      create policy %I on public.%I for select to authenticated using (true);
    $f$, t || '_auth_read', t);
    execute format('drop policy if exists %I on public.%I;', t || '_admin_write', t);
    execute format($f$
      create policy %I on public.%I for all to authenticated
        using (public.is_admin()) with check (public.is_admin());
    $f$, t || '_admin_write', t);
    execute format('drop policy if exists %I on public.%I;', t || '_service', t);
    execute format($f$
      create policy %I on public.%I for all to service_role using (true) with check (true);
    $f$, t || '_service', t);
    execute format('revoke all on public.%I from anon;', t);
  end loop;
end $$;

-- ──────────────────────────────────────────────────────────────────────────
-- GROUP C — server-internal: service_role only, no authenticated access.
--   policy_extraction_locks : extraction-pipeline lock table, never anon-exposed.
--   hr_policies             : legacy table keyed by free-text company_entity that
--                             does not map to a company UUID; locked to backend.
-- ──────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  tables text[] := array['policy_extraction_locks', 'hr_policies'];
begin
  foreach t in array tables loop
    execute format('alter table public.%I enable row level security;', t);
    execute format('drop policy if exists %I on public.%I;', t || '_service', t);
    execute format($f$
      create policy %I on public.%I for all to service_role using (true) with check (true);
    $f$, t || '_service', t);
    execute format('revoke all on public.%I from anon;', t);
  end loop;
end $$;

commit;

-- ============================================================================
-- ROLLBACK (manual): run the block below to fully revert this migration.
-- ============================================================================
-- begin;
-- do $$
-- declare
--   t text;
--   all_tables text[] := array[
--     'company_policies','company_preferred_suppliers','company_policy_assistant_bindings',
--     'policy_assistant_answer_audits','policy_configs','policy_documents','policy_knowledge_snapshots',
--     'company_vendor_selections','policy_document_chunks','policy_document_clauses','policy_processing_runs',
--     'policy_facts','policy_versions','policy_assignment_type_applicability','policy_benefit_rules',
--     'policy_benefit_rule_hr_overrides','policy_evidence_requirements','policy_exclusions',
--     'policy_family_status_applicability','policy_rule_conditions','policy_source_links','policy_tier_overrides',
--     'policy_config_versions','policy_config_benefits','policy_benefit_jurisdiction_overrides',
--     'policy_benefit_rule_hr_override_audit','compliance_actions','compliance_reports',
--     'canonical_policy_documents','canonical_policy_document_chunks','canonical_policy_facts',
--     'canonical_policy_fact_validation_errors','policy_rules','policy_extraction_locks','hr_policies'
--   ];
-- begin
--   foreach t in array all_tables loop
--     execute format('alter table public.%I disable row level security;', t);
--     execute format('drop policy if exists %I on public.%I;', t || '_hr_all', t);
--     execute format('drop policy if exists %I on public.%I;', t || '_auth_read', t);
--     execute format('drop policy if exists %I on public.%I;', t || '_admin_write', t);
--     execute format('drop policy if exists %I on public.%I;', t || '_service', t);
--   end loop;
-- end $$;
-- drop function if exists public.policy_config_version_in_company_scope(uuid);
-- drop function if exists public.policy_version_in_company_scope(uuid);
-- drop function if exists public.hr_company_ids();
-- commit;
-- ============================================================================
