-- ============================================================================
-- SEC-RLSc (AIQ-660) · Tenant-scoped RLS for the rce.* Case Engine schema
-- Parent sprint AIQ-649. Supersedes C1-01a. Branch audit/stage-1c-rce-tenant-rls.
--
-- Replaces the permissive `USING (true)` policies that survived on
-- rce.extraction_agents and rce.agent_versions (the last C1-01 permissive
-- leftovers — any authenticated user could read internal extraction config),
-- and ADDITIVELY introduces tenant-scoped authenticated SELECT across the rce
-- schema per Architecture Report §12.2.
--
-- DESIGN (see audit/execution-prompts/SEC-RLSc-IMPLEMENTATION-SPEC.md):
--  * SAFE-BY-DEFAULT + DRIFT-TOLERANT: §3 drops every existing rce policy
--    (except the deliberately-governed rule_change_proposals), §4a re-locks
--    every rce base table to service_role-only + REVOKE anon, then §4b adds
--    tenant-scoped authenticated SELECT only where a tenant boundary exists.
--    Any table not explicitly scoped stays service-only — never permissive.
--  * SELF-CONTAINED: own rce.* helpers; depends only on public.is_admin()
--    and public.hr_users (verified present in prod 2026-06-03).
--  * PHI AUDIT (option a): Postgres has no BEFORE SELECT trigger, so a
--    SECURITY DEFINER accessor rce.read_phi_field() audits BIOMETRIC/CRIMINAL
--    reads. public.audit_logs.action_type CHECK forbids 'read', so the sink is
--    a dedicated append-only rce.phi_access_log.
--  * LINKAGE: rce.* has no auth-principal linkage yet; this adds provisional
--    columns (rce.employees.auth_user_id, rce.family_members.auth_user_id,
--    rce.employers.company_id). They are EMPTY until C1-05a wires the Case
--    Engine to auth, so authenticated principals see ZERO rce rows until then
--    (safe default). The backend connects as postgres and bypasses RLS, so the
--    FastAPI Case Engine is unaffected.
--
-- DIVERGENCE FROM SPEC (live-schema corrections, verified against prod):
--  * rce.addresses holds street/postal/locality data (applicant address PII),
--    NOT reference data — it is kept service_role-only, NOT authenticated-read.
--  * rce.contradictions and rce.rule_citations both carry case_id and are
--    case-scoped here (they postdate the spec's table list).
--  * rce.rule_change_proposals carries an intentional admin-read policy
--    (AIQ added 2026-06-04) and is PRESERVED untouched — it holds global
--    rule-change governance data, not tenant rows.
--
-- Reversible: rollback block at the foot.
-- ============================================================================

begin;

-- 0. Principal<->tenant linkage columns (provisional; empty until C1-05a).
do $$
begin
  if to_regclass('rce.employees') is not null then
    alter table rce.employees add column if not exists auth_user_id uuid;
    create index if not exists employees_auth_user_id_idx on rce.employees(auth_user_id);
  end if;
  if to_regclass('rce.family_members') is not null then
    alter table rce.family_members add column if not exists auth_user_id uuid;
    create index if not exists family_members_auth_user_id_idx on rce.family_members(auth_user_id);
  end if;
  if to_regclass('rce.employers') is not null then
    alter table rce.employers add column if not exists company_id text;  -- mirrors public.hr_users.company_id (text)
    create index if not exists employers_company_id_idx on rce.employers(company_id);
  end if;
end $$;

-- 1. PHI classification column + dedicated append-only audit sink.
do $$
begin
  if to_regclass('rce.extracted_fields') is not null then
    alter table rce.extracted_fields
      add column if not exists phi_class text not null default 'NONE';
    if not exists (
      select 1 from pg_constraint
       where conname = 'extracted_fields_phi_class_check'
         and conrelid = 'rce.extracted_fields'::regclass
    ) then
      alter table rce.extracted_fields
        add constraint extracted_fields_phi_class_check
        check (phi_class in ('NONE','PII','SENSITIVE','BIOMETRIC','CRIMINAL'));
    end if;
  end if;
end $$;

create table if not exists rce.phi_access_log (
  id                 uuid primary key default gen_random_uuid(),
  principal_id       uuid,                       -- auth.uid() of the reader (NULL if unknown)
  db_role            text not null default current_user,
  action             text not null default 'phi.read',
  extracted_field_id uuid not null,
  phi_class          text not null,
  occurred_at        timestamptz not null default now()
);
create index if not exists phi_access_log_field_idx
  on rce.phi_access_log(extracted_field_id, occurred_at desc);

-- 2. Self-contained tenant-scoping helpers (SECURITY DEFINER, owner=postgres,
--    therefore RLS-bypassing -> no policy recursion).
create or replace function rce.current_hr_company()
  returns text language sql stable security definer set search_path = public, pg_temp as $fn$
  select company_id from public.hr_users where id = (auth.uid())::text limit 1
$fn$;
comment on function rce.current_hr_company() is
  'SEC-RLSc: public.hr_users.company_id (text) for the current auth uid, or NULL.';

create or replace function rce.can_access_case(p_case_id uuid)
  returns boolean language sql stable security definer set search_path = rce, public, pg_temp as $fn$
  select
    public.is_admin()
    or (p_case_id is not null and exists (
      select 1 from rce.cases c
       where c.case_id = p_case_id
         and (
           exists (select 1 from rce.employees e
                    where e.employee_id = c.primary_employee_id
                      and e.auth_user_id = auth.uid())
           or exists (select 1 from rce.employers em
                       where em.employer_id = c.employer_id
                         and em.company_id is not null
                         and em.company_id = rce.current_hr_company())
           or exists (select 1 from rce.family_members fm
                       where fm.case_id = c.case_id
                         and fm.auth_user_id = auth.uid())
         )
    ))
$fn$;
comment on function rce.can_access_case(uuid) is
  'SEC-RLSc: true when current auth uid is the case employee, a linked family '
  'member, a same-company HR operator, or a platform admin.';

create or replace function rce.can_access_employer(p_employer_id uuid)
  returns boolean language sql stable security definer set search_path = rce, public, pg_temp as $fn$
  select
    public.is_admin()
    or (p_employer_id is not null and exists (
      select 1 from rce.employers em
       where em.employer_id = p_employer_id
         and em.company_id is not null
         and em.company_id = rce.current_hr_company()))
$fn$;
comment on function rce.can_access_employer(uuid) is
  'SEC-RLSc: true when current auth uid is a same-company HR operator or admin.';

grant execute on function rce.current_hr_company()       to authenticated, service_role;
grant execute on function rce.can_access_case(uuid)      to authenticated, service_role;
grant execute on function rce.can_access_employer(uuid)  to authenticated, service_role;

-- PHI accessor (option a): access-check then audit sensitive reads.
create or replace function rce.read_phi_field(p_field_id uuid)
  returns rce.extracted_fields
  language plpgsql volatile security definer set search_path = rce, public, pg_temp as $fn$
declare
  rec rce.extracted_fields;
  ok  boolean;
begin
  select * into rec from rce.extracted_fields where extracted_field_id = p_field_id;
  if not found then
    return null;
  end if;
  ok := public.is_admin() or exists (
    select 1 from rce.documents d
     where d.document_id = rec.document_id
       and rce.can_access_case(d.case_id)
  );
  if not ok then
    raise exception 'access denied to rce.extracted_fields %', p_field_id using errcode = '42501';
  end if;
  if rec.phi_class in ('BIOMETRIC','CRIMINAL')
     and current_user not in ('postgres','service_role') then
    insert into rce.phi_access_log (principal_id, db_role, action, extracted_field_id, phi_class)
    values (auth.uid(), current_user, 'phi.read', p_field_id, rec.phi_class);
  end if;
  return rec;
end
$fn$;
comment on function rce.read_phi_field(uuid) is
  'SEC-RLSc: access-checked accessor for extracted_fields; logs BIOMETRIC/CRIMINAL '
  'reads by non-system principals to rce.phi_access_log. Routers MUST use this for '
  'phi_class-flagged reads. -- TODO[C1-05a]: wire FastAPI reads through this fn.';
grant execute on function rce.read_phi_field(uuid) to authenticated, service_role;

-- 3. Drop ALL existing policies in schema rce (clears the C1-01 permissive set
--    + the prior defense-in-depth service-only policies), EXCEPT the
--    deliberately-governed rule_change_proposals (admin-read, kept as-is).
do $$
declare r record;
begin
  for r in
    select policyname, tablename from pg_policies
     where schemaname = 'rce' and tablename <> 'rule_change_proposals'
  loop
    execute format('drop policy if exists %I on rce.%I', r.policyname, r.tablename);
  end loop;
end $$;

-- 4a. Safe default: every rce base table (except the preserved one) -> RLS on,
--     anon revoked, service_role ALL. Authenticated gets NOTHING here.
do $$
declare t text;
begin
  for t in
    select table_name from information_schema.tables
     where table_schema = 'rce' and table_type = 'BASE TABLE'
       and table_name <> 'rule_change_proposals'
  loop
    execute format('alter table rce.%I enable row level security', t);
    execute format('revoke all on rce.%I from anon', t);
    execute format('drop policy if exists %I on rce.%I', t || '_service_all', t);
    execute format(
      'create policy %I on rce.%I for all to service_role using (true) with check (true)',
      t || '_service_all', t);
  end loop;
end $$;

-- 4b. Additive authenticated SELECT policies (tenant-scoped).

-- (i) Case-anchored tables with a direct case_id column.
do $$
declare
  t text;
  case_tables text[] := array[
    'family_members','documents','deadlines','costs','corrections',
    'agent_runs','case_artefacts','policy_gaps','contradictions','rule_citations'
  ];
begin
  foreach t in array case_tables loop
    if to_regclass('rce.'||t) is not null
       and exists (select 1 from information_schema.columns
                    where table_schema='rce' and table_name=t and column_name='case_id') then
      execute format('drop policy if exists %I on rce.%I', t||'_tenant_select', t);
      execute format(
        'create policy %I on rce.%I for select to authenticated using (rce.can_access_case(case_id))',
        t||'_tenant_select', t);
    end if;
  end loop;
end $$;

-- (ii) cases anchor (pk = case_id).
do $$ begin
  if to_regclass('rce.cases') is not null then
    drop policy if exists cases_tenant_select on rce.cases;
    create policy cases_tenant_select on rce.cases
      for select to authenticated using (rce.can_access_case(case_id));
  end if;
end $$;

-- (iii) employer-scoped: employers / employees / hr_policies / policy_clauses.
do $$ begin
  if to_regclass('rce.employers') is not null then
    drop policy if exists employers_tenant_select on rce.employers;
    create policy employers_tenant_select on rce.employers
      for select to authenticated using (rce.can_access_employer(employer_id));
  end if;

  if to_regclass('rce.employees') is not null then
    drop policy if exists employees_tenant_select on rce.employees;
    create policy employees_tenant_select on rce.employees
      for select to authenticated using (
        public.is_admin()
        or auth_user_id = auth.uid()
        or exists (select 1 from rce.cases c
                    where c.primary_employee_id = employees.employee_id
                      and rce.can_access_case(c.case_id))
      );
  end if;

  if to_regclass('rce.hr_policies') is not null then
    drop policy if exists hr_policies_tenant_select on rce.hr_policies;
    create policy hr_policies_tenant_select on rce.hr_policies
      for select to authenticated using (rce.can_access_employer(employer_id));
  end if;

  if to_regclass('rce.policy_clauses') is not null then
    drop policy if exists policy_clauses_tenant_select on rce.policy_clauses;
    create policy policy_clauses_tenant_select on rce.policy_clauses
      for select to authenticated using (
        exists (select 1 from rce.hr_policies hp
                 where hp.hr_policy_id = policy_clauses.hr_policy_id
                   and rce.can_access_employer(hp.employer_id))
      );
  end if;
end $$;

-- (iv) transitively case-scoped: extracted_fields, entity_links.
do $$ begin
  if to_regclass('rce.extracted_fields') is not null then
    drop policy if exists extracted_fields_tenant_select on rce.extracted_fields;
    create policy extracted_fields_tenant_select on rce.extracted_fields
      for select to authenticated using (
        exists (select 1 from rce.documents d
                 where d.document_id = extracted_fields.document_id
                   and rce.can_access_case(d.case_id))
      );
  end if;

  if to_regclass('rce.entity_links') is not null then
    drop policy if exists entity_links_tenant_select on rce.entity_links;
    create policy entity_links_tenant_select on rce.entity_links
      for select to authenticated using (
        exists (select 1
                  from rce.extracted_fields ef
                  join rce.documents d on d.document_id = ef.document_id
                 where ef.extracted_field_id = entity_links.extracted_field_id
                   and rce.can_access_case(d.case_id))
      );
  end if;
end $$;

-- (v) non-tenant, non-PII reference/config tables -> authenticated read.
--     NOTE: rce.addresses is deliberately EXCLUDED — it holds applicant
--     street/postal address PII, not reference data, so it stays service-only.
do $$
declare
  t text;
  ref_tables text[] := array[
    'document_types','rules','rule_versions','steps','authorities'
  ];
begin
  foreach t in array ref_tables loop
    if to_regclass('rce.'||t) is not null then
      execute format('drop policy if exists %I on rce.%I', t||'_ref_read', t);
      execute format(
        'create policy %I on rce.%I for select to authenticated using (true)',
        t||'_ref_read', t);
    end if;
  end loop;
end $$;

-- INTENTIONALLY service_role-only (no authenticated policy), documented:
--   * rce.addresses          -> applicant address PII, no tenant column.
--   * rce.canonical_entities -> cross-case PII identity graph, no tenant column.
--   * rce.extraction_agents  -> internal extraction config (was permissive; now locked).
--   * rce.agent_versions     -> internal extraction telemetry/config (was permissive; now locked).
-- They are backend-mediated; leaving them service-only is deliberate, not an omission.

-- phi_access_log: admins may read; writes only via the SECURITY DEFINER fn / service.
do $$ begin
  drop policy if exists phi_access_log_admin_read on rce.phi_access_log;
  create policy phi_access_log_admin_read on rce.phi_access_log
    for select to authenticated using (public.is_admin());
end $$;

commit;

-- ============================================================================
-- ROLLBACK (manual):
-- begin;
--   do $$ declare r record; begin
--     for r in select policyname, tablename from pg_policies
--               where schemaname='rce' and tablename <> 'rule_change_proposals' loop
--       execute format('drop policy if exists %I on rce.%I', r.policyname, r.tablename);
--     end loop;
--   end $$;
--   drop function if exists rce.read_phi_field(uuid);
--   drop function if exists rce.can_access_employer(uuid);
--   drop function if exists rce.can_access_case(uuid);
--   drop function if exists rce.current_hr_company();
--   drop table if exists rce.phi_access_log;
--   -- Added columns (auth_user_id x2, employers.company_id, extracted_fields.phi_class)
--   -- are harmless to keep; drop only if strictly required.
--   -- NOTE: reverting to permissive USING(true) is NOT provided on purpose — that
--   -- was the exposure this task removes.
-- commit;
-- ============================================================================
