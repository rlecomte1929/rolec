-- ============================================================================
-- SEC-RLSa (AIQ-658) · RLS for the Cases domain
-- Parent sprint AIQ-649 — Complete RLS coverage.
--
-- Adds tenant-scoped Row Level Security to every cases / assignment-scoped
-- table on supabase/rls_allowlist.txt that belongs to the cases domain (28
-- tables). Pattern reference: 20260325000000_case_milestones.sql and the
-- existing case_messages / relocation_cases policies.
--
-- Tenancy model (two coexisting case systems in this schema):
--   • Legacy text-keyed system: public.case_assignments
--       (id, case_id, canonical_case_id, employee_user_id, hr_user_id) and
--       public.relocation_cases (id uuid, employee_id, hr_user_id, company_id).
--       The Supabase auth uid is stored AS TEXT in *_user_id columns and in
--       hr_users.id / employees.id (see case_milestones + relocation_cases B5
--       policies). HR are scoped company-wide via hr_users.company_id.
--   • Newer uuid-keyed system: public.cases (id, employee_id uuid = auth.uid(),
--       company_id uuid). Scoped with the existing my_role()/my_company_id()
--       helpers, identical to the live cases_* policies.
--
-- These tables are NOT read by the frontend through the Supabase anon client
-- (verified: no `.from('<table>')` calls in frontend/src). They are mediated by
-- the FastAPI backend, which connects via DATABASE_URL as the `postgres` role
-- and therefore bypasses RLS. RLS here is the defense-in-depth boundary that
-- stops the public anon key (shipped in the frontend bundle) from reading the
-- `public` schema via PostgREST — the SEC-002 failure mode.
--
-- Reversible: see the rollback block at the foot of this file.
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- Tenant-scoping helper functions.
--
-- SECURITY DEFINER + owned by the migration role (postgres) so they bypass RLS
-- on case_assignments / hr_users / relocation_cases / cases. This is required:
--   1. to avoid RLS recursion (a policy on table X that selects case_assignments
--      must not itself be filtered), and
--   2. so HR company membership can be resolved regardless of the (separate)
--      RLS on those parent tables.
-- auth.uid() reads the request JWT GUC and is unaffected by SECURITY DEFINER.
-- STABLE: result is constant within a single statement for a given uid.
-- ----------------------------------------------------------------------------

create or replace function public.rls_current_hr_company()
  returns text
  language sql
  stable
  security definer
  set search_path = public, pg_temp
as $$
  select company_id
    from public.hr_users
   where id = (auth.uid())::text
   limit 1
$$;

comment on function public.rls_current_hr_company() is
  'SEC-RLSa: legacy hr_users.company_id (text) for the current auth uid, or NULL.';

-- Access to a legacy assignment-scoped row (param = case_assignments.id).
create or replace function public.rls_can_access_assignment(p_assignment_id text)
  returns boolean
  language sql
  stable
  security definer
  set search_path = public, pg_temp
as $$
  select
    public.is_admin()
    or (p_assignment_id is not null and exists (
      select 1
        from public.case_assignments ca
       where ca.id = p_assignment_id
         and (
           ca.employee_user_id = (auth.uid())::text
           or ca.hr_user_id = (auth.uid())::text
           or ca.hr_user_id in (
             select h.id from public.hr_users h
              where h.company_id = public.rls_current_hr_company()
           )
         )
    ))
$$;

comment on function public.rls_can_access_assignment(text) is
  'SEC-RLSa: true when the current auth uid is the employee, the owning HR, a '
  'same-company HR, or an admin for the given case_assignments.id.';

-- Access to a legacy case-scoped row (param matched against
-- case_assignments.case_id / .canonical_case_id, and relocation_cases.id::text).
create or replace function public.rls_can_access_case_ref(p_case_id text)
  returns boolean
  language sql
  stable
  security definer
  set search_path = public, pg_temp
as $$
  select
    public.is_admin()
    or (p_case_id is not null and exists (
      select 1
        from public.case_assignments ca
       where (ca.case_id = p_case_id or ca.canonical_case_id = p_case_id)
         and (
           ca.employee_user_id = (auth.uid())::text
           or ca.hr_user_id = (auth.uid())::text
           or ca.hr_user_id in (
             select h.id from public.hr_users h
              where h.company_id = public.rls_current_hr_company()
           )
         )
    ))
    or (p_case_id is not null and exists (
      select 1
        from public.relocation_cases rc
       where rc.id::text = p_case_id
         and (
           rc.employee_id = (auth.uid())::text
           or rc.hr_user_id = (auth.uid())::text
           or rc.company_id = public.rls_current_hr_company()
         )
    ))
$$;

comment on function public.rls_can_access_case_ref(text) is
  'SEC-RLSa: true when the current auth uid is the employee, a same-company HR, '
  'or an admin for the given legacy case_id / canonical_case_id.';

-- Access to a uuid-keyed mobility_cases row (param = mobility_cases.id). The
-- uuid case tables (case_documents, case_people, case_requirement_evaluations)
-- FK their case_id to public.mobility_cases, whose owner columns are
-- employee_user_id (uuid = auth.uid()) and company_id (uuid). HR is resolved via
-- the profiles helpers, mirroring the live cases_* policies.
create or replace function public.rls_can_access_case_uuid(p_case_id uuid)
  returns boolean
  language sql
  stable
  security definer
  set search_path = public, pg_temp
as $$
  select
    public.is_admin()
    or (p_case_id is not null and exists (
      select 1
        from public.mobility_cases mc
       where mc.id = p_case_id
         and (
           mc.employee_user_id = auth.uid()
           or (public.my_role() = any (array['hr','admin'])
               and mc.company_id = public.my_company_id())
         )
    ))
$$;

comment on function public.rls_can_access_case_uuid(uuid) is
  'SEC-RLSa: true when the current auth uid is the employee, a same-company HR, '
  'or an admin for the given mobility_cases.id (uuid system).';

-- Access to a resolved-policy child row (param = resolved_assignment_policies.id).
create or replace function public.rls_can_access_resolved_policy(p_resolved_policy_id uuid)
  returns boolean
  language sql
  stable
  security definer
  set search_path = public, pg_temp
as $$
  select
    public.is_admin()
    or (p_resolved_policy_id is not null and exists (
      select 1
        from public.resolved_assignment_policies r
       where r.id = p_resolved_policy_id
         and (
           public.rls_can_access_assignment(r.assignment_id)
           or public.rls_can_access_case_ref(r.case_id)
           or (r.company_id is not null
               and r.company_id = public.rls_current_hr_company())
         )
    ))
$$;

comment on function public.rls_can_access_resolved_policy(uuid) is
  'SEC-RLSa: true when the current auth uid can access the parent '
  'resolved_assignment_policies row.';

grant execute on function public.rls_current_hr_company() to authenticated, service_role;
grant execute on function public.rls_can_access_assignment(text) to authenticated, service_role;
grant execute on function public.rls_can_access_case_ref(text) to authenticated, service_role;
grant execute on function public.rls_can_access_case_uuid(uuid) to authenticated, service_role;
grant execute on function public.rls_can_access_resolved_policy(uuid) to authenticated, service_role;

-- ----------------------------------------------------------------------------
-- Ghost-table reconstruction (prod-as-oracle, idempotent).
-- The RLS blocks below enable RLS on assignment_audit_log, eligibility_overrides,
-- employee_answers, case_requirements_snapshots, profile_state, answers,
-- case_assignment_id, and wizard_cases — but those tables were created out-of-band
-- on prod by the backend (SQLAlchemy ORM / direct DDL) and have no repo CREATE,
-- so a fresh replay / Supabase Preview hits "relation does not exist" before the
-- RLS loop. Recreate them here exactly as they live on prod (column types,
-- PK, indexes verified against information_schema + pg_get_constraintdef on
-- 2026-06-01). On prod every statement is a no-op (IF NOT EXISTS); RLS, policies,
-- and `revoke ... from anon` are applied by the blocks below. None of these tables
-- carry FKs, so creation order is unconstrained.

create table if not exists public.assignment_audit_log (
  id            uuid        not null default gen_random_uuid(),
  assignment_id text        not null,
  actor_user_id uuid        not null,
  action        text        not null,
  from_status   text,
  to_status     text,
  created_at    timestamptz not null default now(),
  metadata      jsonb       not null default '{}'::jsonb,
  constraint assignment_audit_log_pkey primary key (id)
);
create index if not exists assignment_audit_log_actor_user_id_idx
  on public.assignment_audit_log (actor_user_id);
create index if not exists assignment_audit_log_assignment_id_idx
  on public.assignment_audit_log (assignment_id);

create table if not exists public.eligibility_overrides (
  id                 text    not null,
  assignment_id      text    not null,
  category           text    not null,
  allowed            integer not null default 1,
  expires_at         text,
  note               text,
  created_by_user_id text    not null,
  created_at         text    not null,
  constraint eligibility_overrides_pkey primary key (id)
);

create table if not exists public.employee_answers (
  id            serial  primary key,
  assignment_id text    not null,
  question_id   text    not null,
  answer_json   text    not null,
  created_at    text    not null
);

create table if not exists public.case_requirements_snapshots (
  id                varchar   not null,
  case_id           varchar,
  dest_country      varchar   not null,
  purpose           varchar   not null,
  created_at        timestamp not null,
  snapshot_json     text      not null,
  sources_json      text      not null,
  canonical_case_id text,
  constraint case_requirements_snapshots_pkey primary key (id)
);
create index if not exists ix_case_requirements_snapshots_case_id
  on public.case_requirements_snapshots (case_id);
create index if not exists ix_case_requirements_snapshots_id
  on public.case_requirements_snapshots (id);

create table if not exists public.profile_state (
  user_id      text not null,
  profile_json text not null,
  updated_at   text not null,
  constraint profile_state_pkey primary key (user_id)
);

create table if not exists public.answers (
  id          serial  primary key,
  user_id     text    not null,
  question_id text    not null,
  answer_json text    not null,
  is_unknown  integer not null default 0,
  created_at  text    not null
);

create table if not exists public.case_assignment_id (
  id         bigint      not null,
  created_at timestamptz not null default now(),
  constraint case_assignment_id_pkey primary key (id)
);

create table if not exists public.wizard_cases (
  id                       varchar   not null,
  draft_json               text      not null,
  created_at               timestamp not null default now(),
  updated_at               timestamp not null default now(),
  origin_country           varchar,
  origin_city              varchar,
  dest_country             varchar,
  dest_city                varchar,
  purpose                  varchar,
  target_move_date         date,
  flags_json               text,
  status                   varchar   not null,
  requirements_snapshot_id varchar,
  constraint wizard_cases_pkey primary key (id)
);
create index if not exists ix_wizard_cases_id on public.wizard_cases (id);

-- ----------------------------------------------------------------------------
-- uuid `cases` system tables — scoped via rls_can_access_case_uuid(case_id).
-- ----------------------------------------------------------------------------

alter table public.case_documents enable row level security;
drop policy if exists case_documents_tenant_rw on public.case_documents;
create policy case_documents_tenant_rw on public.case_documents for all to authenticated
  using (public.rls_can_access_case_uuid(case_id))
  with check (public.rls_can_access_case_uuid(case_id));
drop policy if exists case_documents_service on public.case_documents;
create policy case_documents_service on public.case_documents for all to service_role
  using (true) with check (true);
revoke all on public.case_documents from anon;

alter table public.case_people enable row level security;
drop policy if exists case_people_tenant_rw on public.case_people;
create policy case_people_tenant_rw on public.case_people for all to authenticated
  using (public.rls_can_access_case_uuid(case_id))
  with check (public.rls_can_access_case_uuid(case_id));
drop policy if exists case_people_service on public.case_people;
create policy case_people_service on public.case_people for all to service_role
  using (true) with check (true);
revoke all on public.case_people from anon;

alter table public.case_requirement_evaluations enable row level security;
drop policy if exists case_requirement_evaluations_tenant_rw on public.case_requirement_evaluations;
create policy case_requirement_evaluations_tenant_rw on public.case_requirement_evaluations for all to authenticated
  using (public.rls_can_access_case_uuid(case_id))
  with check (public.rls_can_access_case_uuid(case_id));
drop policy if exists case_requirement_evaluations_service on public.case_requirement_evaluations;
create policy case_requirement_evaluations_service on public.case_requirement_evaluations for all to service_role
  using (true) with check (true);
revoke all on public.case_requirement_evaluations from anon;

-- ----------------------------------------------------------------------------
-- Legacy assignment_id-keyed tables — scoped via rls_can_access_assignment().
-- ----------------------------------------------------------------------------

alter table public.case_readiness enable row level security;
drop policy if exists case_readiness_tenant_rw on public.case_readiness;
create policy case_readiness_tenant_rw on public.case_readiness for all to authenticated
  using (public.rls_can_access_assignment(assignment_id))
  with check (public.rls_can_access_assignment(assignment_id));
drop policy if exists case_readiness_service on public.case_readiness;
create policy case_readiness_service on public.case_readiness for all to service_role
  using (true) with check (true);
revoke all on public.case_readiness from anon;

alter table public.case_readiness_checklist_state enable row level security;
drop policy if exists case_readiness_checklist_state_tenant_rw on public.case_readiness_checklist_state;
create policy case_readiness_checklist_state_tenant_rw on public.case_readiness_checklist_state for all to authenticated
  using (public.rls_can_access_assignment(assignment_id))
  with check (public.rls_can_access_assignment(assignment_id));
drop policy if exists case_readiness_checklist_state_service on public.case_readiness_checklist_state;
create policy case_readiness_checklist_state_service on public.case_readiness_checklist_state for all to service_role
  using (true) with check (true);
revoke all on public.case_readiness_checklist_state from anon;

alter table public.case_readiness_milestone_state enable row level security;
drop policy if exists case_readiness_milestone_state_tenant_rw on public.case_readiness_milestone_state;
create policy case_readiness_milestone_state_tenant_rw on public.case_readiness_milestone_state for all to authenticated
  using (public.rls_can_access_assignment(assignment_id))
  with check (public.rls_can_access_assignment(assignment_id));
drop policy if exists case_readiness_milestone_state_service on public.case_readiness_milestone_state;
create policy case_readiness_milestone_state_service on public.case_readiness_milestone_state for all to service_role
  using (true) with check (true);
revoke all on public.case_readiness_milestone_state from anon;

alter table public.assignment_audit_log enable row level security;
drop policy if exists assignment_audit_log_tenant_rw on public.assignment_audit_log;
create policy assignment_audit_log_tenant_rw on public.assignment_audit_log for all to authenticated
  using (public.rls_can_access_assignment(assignment_id))
  with check (public.rls_can_access_assignment(assignment_id));
drop policy if exists assignment_audit_log_service on public.assignment_audit_log;
create policy assignment_audit_log_service on public.assignment_audit_log for all to service_role
  using (true) with check (true);
revoke all on public.assignment_audit_log from anon;

alter table public.assignment_mobility_links enable row level security;
drop policy if exists assignment_mobility_links_tenant_rw on public.assignment_mobility_links;
create policy assignment_mobility_links_tenant_rw on public.assignment_mobility_links for all to authenticated
  using (public.rls_can_access_assignment(assignment_id))
  with check (public.rls_can_access_assignment(assignment_id));
drop policy if exists assignment_mobility_links_service on public.assignment_mobility_links;
create policy assignment_mobility_links_service on public.assignment_mobility_links for all to service_role
  using (true) with check (true);
revoke all on public.assignment_mobility_links from anon;

alter table public.eligibility_overrides enable row level security;
drop policy if exists eligibility_overrides_tenant_rw on public.eligibility_overrides;
create policy eligibility_overrides_tenant_rw on public.eligibility_overrides for all to authenticated
  using (public.rls_can_access_assignment(assignment_id))
  with check (public.rls_can_access_assignment(assignment_id));
drop policy if exists eligibility_overrides_service on public.eligibility_overrides;
create policy eligibility_overrides_service on public.eligibility_overrides for all to service_role
  using (true) with check (true);
revoke all on public.eligibility_overrides from anon;

alter table public.employee_answers enable row level security;
drop policy if exists employee_answers_tenant_rw on public.employee_answers;
create policy employee_answers_tenant_rw on public.employee_answers for all to authenticated
  using (public.rls_can_access_assignment(assignment_id))
  with check (public.rls_can_access_assignment(assignment_id));
drop policy if exists employee_answers_service on public.employee_answers;
create policy employee_answers_service on public.employee_answers for all to service_role
  using (true) with check (true);
revoke all on public.employee_answers from anon;

-- ----------------------------------------------------------------------------
-- Legacy case_id / canonical_case_id-keyed tables — rls_can_access_case_ref().
-- ----------------------------------------------------------------------------

alter table public.case_participants enable row level security;
drop policy if exists case_participants_tenant_rw on public.case_participants;
create policy case_participants_tenant_rw on public.case_participants for all to authenticated
  using (public.rls_can_access_case_ref(case_id) or public.rls_can_access_case_ref(canonical_case_id))
  with check (public.rls_can_access_case_ref(case_id) or public.rls_can_access_case_ref(canonical_case_id));
drop policy if exists case_participants_service on public.case_participants;
create policy case_participants_service on public.case_participants for all to service_role
  using (true) with check (true);
revoke all on public.case_participants from anon;

alter table public.case_requirements_snapshots enable row level security;
drop policy if exists case_requirements_snapshots_tenant_rw on public.case_requirements_snapshots;
create policy case_requirements_snapshots_tenant_rw on public.case_requirements_snapshots for all to authenticated
  using (public.rls_can_access_case_ref(case_id) or public.rls_can_access_case_ref(canonical_case_id))
  with check (public.rls_can_access_case_ref(case_id) or public.rls_can_access_case_ref(canonical_case_id));
drop policy if exists case_requirements_snapshots_service on public.case_requirements_snapshots;
create policy case_requirements_snapshots_service on public.case_requirements_snapshots for all to service_role
  using (true) with check (true);
revoke all on public.case_requirements_snapshots from anon;

alter table public.relocation_artifacts enable row level security;
drop policy if exists relocation_artifacts_tenant_rw on public.relocation_artifacts;
create policy relocation_artifacts_tenant_rw on public.relocation_artifacts for all to authenticated
  using (public.rls_can_access_case_ref(case_id))
  with check (public.rls_can_access_case_ref(case_id));
drop policy if exists relocation_artifacts_service on public.relocation_artifacts;
create policy relocation_artifacts_service on public.relocation_artifacts for all to service_role
  using (true) with check (true);
revoke all on public.relocation_artifacts from anon;

alter table public.relocation_runs enable row level security;
drop policy if exists relocation_runs_tenant_rw on public.relocation_runs;
create policy relocation_runs_tenant_rw on public.relocation_runs for all to authenticated
  using (public.rls_can_access_case_ref(case_id))
  with check (public.rls_can_access_case_ref(case_id));
drop policy if exists relocation_runs_service on public.relocation_runs;
create policy relocation_runs_service on public.relocation_runs for all to service_role
  using (true) with check (true);
revoke all on public.relocation_runs from anon;

alter table public.relocation_sources enable row level security;
drop policy if exists relocation_sources_tenant_rw on public.relocation_sources;
create policy relocation_sources_tenant_rw on public.relocation_sources for all to authenticated
  using (public.rls_can_access_case_ref(case_id))
  with check (public.rls_can_access_case_ref(case_id));
drop policy if exists relocation_sources_service on public.relocation_sources;
create policy relocation_sources_service on public.relocation_sources for all to service_role
  using (true) with check (true);
revoke all on public.relocation_sources from anon;

-- ----------------------------------------------------------------------------
-- Tables carrying both assignment_id and case_id/canonical_case_id.
-- ----------------------------------------------------------------------------

alter table public.case_evidence enable row level security;
drop policy if exists case_evidence_tenant_rw on public.case_evidence;
create policy case_evidence_tenant_rw on public.case_evidence for all to authenticated
  using (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or public.rls_can_access_case_ref(canonical_case_id)
  )
  with check (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or public.rls_can_access_case_ref(canonical_case_id)
  );
drop policy if exists case_evidence_service on public.case_evidence;
create policy case_evidence_service on public.case_evidence for all to service_role
  using (true) with check (true);
revoke all on public.case_evidence from anon;

alter table public.case_feedback enable row level security;
drop policy if exists case_feedback_tenant_rw on public.case_feedback;
create policy case_feedback_tenant_rw on public.case_feedback for all to authenticated
  using (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or public.rls_can_access_case_ref(canonical_case_id)
  )
  with check (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or public.rls_can_access_case_ref(canonical_case_id)
  );
drop policy if exists case_feedback_service on public.case_feedback;
create policy case_feedback_service on public.case_feedback for all to service_role
  using (true) with check (true);
revoke all on public.case_feedback from anon;

alter table public.assignment_policy_service_comparisons enable row level security;
drop policy if exists assignment_policy_service_comparisons_tenant_rw on public.assignment_policy_service_comparisons;
create policy assignment_policy_service_comparisons_tenant_rw on public.assignment_policy_service_comparisons for all to authenticated
  using (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or public.rls_can_access_case_ref(canonical_case_id)
  )
  with check (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or public.rls_can_access_case_ref(canonical_case_id)
  );
drop policy if exists assignment_policy_service_comparisons_service on public.assignment_policy_service_comparisons;
create policy assignment_policy_service_comparisons_service on public.assignment_policy_service_comparisons for all to service_role
  using (true) with check (true);
revoke all on public.assignment_policy_service_comparisons from anon;

-- ----------------------------------------------------------------------------
-- Resolved assignment policies (+ children scoped via the parent row).
-- ----------------------------------------------------------------------------

alter table public.resolved_assignment_policies enable row level security;
drop policy if exists resolved_assignment_policies_tenant_rw on public.resolved_assignment_policies;
create policy resolved_assignment_policies_tenant_rw on public.resolved_assignment_policies for all to authenticated
  using (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or (company_id is not null and company_id = public.rls_current_hr_company())
  )
  with check (
    public.rls_can_access_assignment(assignment_id)
    or public.rls_can_access_case_ref(case_id)
    or (company_id is not null and company_id = public.rls_current_hr_company())
  );
drop policy if exists resolved_assignment_policies_service on public.resolved_assignment_policies;
create policy resolved_assignment_policies_service on public.resolved_assignment_policies for all to service_role
  using (true) with check (true);
revoke all on public.resolved_assignment_policies from anon;

alter table public.resolved_assignment_policy_benefits enable row level security;
drop policy if exists resolved_assignment_policy_benefits_tenant_rw on public.resolved_assignment_policy_benefits;
create policy resolved_assignment_policy_benefits_tenant_rw on public.resolved_assignment_policy_benefits for all to authenticated
  using (public.rls_can_access_resolved_policy(resolved_policy_id))
  with check (public.rls_can_access_resolved_policy(resolved_policy_id));
drop policy if exists resolved_assignment_policy_benefits_service on public.resolved_assignment_policy_benefits;
create policy resolved_assignment_policy_benefits_service on public.resolved_assignment_policy_benefits for all to service_role
  using (true) with check (true);
revoke all on public.resolved_assignment_policy_benefits from anon;

alter table public.resolved_assignment_policy_exclusions enable row level security;
drop policy if exists resolved_assignment_policy_exclusions_tenant_rw on public.resolved_assignment_policy_exclusions;
create policy resolved_assignment_policy_exclusions_tenant_rw on public.resolved_assignment_policy_exclusions for all to authenticated
  using (public.rls_can_access_resolved_policy(resolved_policy_id))
  with check (public.rls_can_access_resolved_policy(resolved_policy_id));
drop policy if exists resolved_assignment_policy_exclusions_service on public.resolved_assignment_policy_exclusions;
create policy resolved_assignment_policy_exclusions_service on public.resolved_assignment_policy_exclusions for all to service_role
  using (true) with check (true);
revoke all on public.resolved_assignment_policy_exclusions from anon;

-- ----------------------------------------------------------------------------
-- User-scoped legacy state — owner is the auth uid stored as text.
-- ----------------------------------------------------------------------------

alter table public.profile_state enable row level security;
drop policy if exists profile_state_owner_rw on public.profile_state;
create policy profile_state_owner_rw on public.profile_state for all to authenticated
  using (user_id = (auth.uid())::text or public.is_admin())
  with check (user_id = (auth.uid())::text or public.is_admin());
drop policy if exists profile_state_service on public.profile_state;
create policy profile_state_service on public.profile_state for all to service_role
  using (true) with check (true);
revoke all on public.profile_state from anon;

alter table public.answers enable row level security;
drop policy if exists answers_owner_rw on public.answers;
create policy answers_owner_rw on public.answers for all to authenticated
  using (user_id = (auth.uid())::text or public.is_admin())
  with check (user_id = (auth.uid())::text or public.is_admin());
drop policy if exists answers_service on public.answers;
create policy answers_service on public.answers for all to service_role
  using (true) with check (true);
revoke all on public.answers from anon;

-- ----------------------------------------------------------------------------
-- Readiness templates — NOT tenant data. Public-read for any authenticated
-- user; writes restricted to admins. (Per execution prompt.)
-- ----------------------------------------------------------------------------

alter table public.readiness_templates enable row level security;
drop policy if exists readiness_templates_read on public.readiness_templates;
create policy readiness_templates_read on public.readiness_templates for select to authenticated
  using (true);
drop policy if exists readiness_templates_admin_write on public.readiness_templates;
create policy readiness_templates_admin_write on public.readiness_templates for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
drop policy if exists readiness_templates_service on public.readiness_templates;
create policy readiness_templates_service on public.readiness_templates for all to service_role
  using (true) with check (true);
revoke all on public.readiness_templates from anon;

alter table public.readiness_template_checklist_items enable row level security;
drop policy if exists readiness_template_checklist_items_read on public.readiness_template_checklist_items;
create policy readiness_template_checklist_items_read on public.readiness_template_checklist_items for select to authenticated
  using (true);
drop policy if exists readiness_template_checklist_items_admin_write on public.readiness_template_checklist_items;
create policy readiness_template_checklist_items_admin_write on public.readiness_template_checklist_items for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
drop policy if exists readiness_template_checklist_items_service on public.readiness_template_checklist_items;
create policy readiness_template_checklist_items_service on public.readiness_template_checklist_items for all to service_role
  using (true) with check (true);
revoke all on public.readiness_template_checklist_items from anon;

alter table public.readiness_template_milestones enable row level security;
drop policy if exists readiness_template_milestones_read on public.readiness_template_milestones;
create policy readiness_template_milestones_read on public.readiness_template_milestones for select to authenticated
  using (true);
drop policy if exists readiness_template_milestones_admin_write on public.readiness_template_milestones;
create policy readiness_template_milestones_admin_write on public.readiness_template_milestones for all to authenticated
  using (public.is_admin()) with check (public.is_admin());
drop policy if exists readiness_template_milestones_service on public.readiness_template_milestones;
create policy readiness_template_milestones_service on public.readiness_template_milestones for all to service_role
  using (true) with check (true);
revoke all on public.readiness_template_milestones from anon;

-- ----------------------------------------------------------------------------
-- Server-role-only tables — no tenant/owner column to scope by.
--   • case_assignment_id : an (id bigint, created_at) sequence/counter table,
--     no PII, written only by the backend ID allocator.
--   • wizard_cases       : pre-auth wizard draft state keyed by an opaque
--     wizard id, with no owner column. Backend-mediated; not exposed to the
--     anon client. RLS-enabled + anon revoked closes the PostgREST hole; the
--     backend (postgres role) and service_role retain full access.
-- ----------------------------------------------------------------------------

alter table public.case_assignment_id enable row level security;
drop policy if exists case_assignment_id_service on public.case_assignment_id;
create policy case_assignment_id_service on public.case_assignment_id for all to service_role
  using (true) with check (true);
revoke all on public.case_assignment_id from anon;

alter table public.wizard_cases enable row level security;
drop policy if exists wizard_cases_service on public.wizard_cases;
create policy wizard_cases_service on public.wizard_cases for all to service_role
  using (true) with check (true);
revoke all on public.wizard_cases from anon;

commit;

-- ============================================================================
-- ROLLBACK (manual) — run inside a transaction to fully revert this migration:
--
-- begin;
--   -- Drop policies + disable RLS on every table touched above.
--   do $$
--   declare t text;
--   begin
--     foreach t in array array[
--       'case_documents','case_people','case_requirement_evaluations',
--       'case_readiness','case_readiness_checklist_state','case_readiness_milestone_state',
--       'assignment_audit_log','assignment_mobility_links','eligibility_overrides',
--       'employee_answers','case_participants','case_requirements_snapshots',
--       'relocation_artifacts','relocation_runs','relocation_sources',
--       'case_evidence','case_feedback','assignment_policy_service_comparisons',
--       'resolved_assignment_policies','resolved_assignment_policy_benefits',
--       'resolved_assignment_policy_exclusions','profile_state','answers',
--       'readiness_templates','readiness_template_checklist_items',
--       'readiness_template_milestones','case_assignment_id','wizard_cases'
--     ]
--     loop
--       execute format('alter table public.%I disable row level security;', t);
--       -- (policies are dropped automatically on DISABLE only if dropped first;
--       --  drop them explicitly if re-running this file later via the
--       --  `drop policy if exists` statements above.)
--     end loop;
--   end $$;
--   drop function if exists public.rls_can_access_resolved_policy(uuid);
--   drop function if exists public.rls_can_access_case_uuid(uuid);
--   drop function if exists public.rls_can_access_case_ref(text);
--   drop function if exists public.rls_can_access_assignment(text);
--   drop function if exists public.rls_current_hr_company();
-- commit;
-- ============================================================================
