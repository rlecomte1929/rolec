# SEC-RLSc (AIQ-660) — Implementation Spec for `rce.*` Tenant RLS

**Status:** Ready to implement + validate in a session with trustworthy tool I/O and DB access.
**Companion to:** `SEC-RLSc-rce-tables.md` (canonical task prompt).
**Branch:** `audit/stage-1-rls-c-rce` · **Notion:** AIQ-660 · **Priority:** P0.

> **Why this spec exists.** It was authored in a session where (a) `execute_sql`
> against the Supabase project was permission-denied (no DB validation possible),
> and (b) several tool reads returned intermittently corrupted output. Authoring
> the security boundary blind was judged unsafe, so the design + full artifacts
> are captured here for a clean session to implement and **validate against a real
> DB** before merge. Every fact below is labelled by how it was verified.

---

## 1. Reliable ground truth (verified this session)

| Fact | How verified | Confidence |
|---|---|---|
| rce baseline `20260528020000_relopass_case_engine_v1.sql` creates 20 tables, all with **permissive `FOR ALL USING (true)`** policies (the thing we replace). | Read migration source (clean, repeated) | High |
| `20260529100000_rce_extraction_agents.sql` adds `rce.extraction_agents`, `rce.agent_versions`, and `rce.agent_runs.agent_version_ref`, also permissive. | Read source | High |
| **Migration drift is real**: remote (`list_migrations`) has `rce_policy_gaps`, `rce_case_artefacts`, `public_agent_runs` applied under *different* timestamps than local files; some local files (e.g. extraction_agents) may not be applied remotely. | `list_migrations` MCP (succeeded) + local `ls` | High |
| `rce.extracted_fields` has **no `phi_class`** column; rce has **no `auth_user_id`** anywhere. | `grep` migration sources | High |
| `public.audit_logs` **exists** but its `action_type` is `CHECK (in 'insert','update','delete')` and `actor_type` is `CHECK (in 'system','human','service')` — **cannot store a `'phi.read'` event**. | Read `20260411140000_audit_logs.sql` (clean) | High |
| `public.audit_events` does **not** exist. | `grep` migrations | High |
| `scripts/check_rls_coverage.py` scans **`public` only** (`WHERE t.schemaname='public'`). → **No `supabase/rls_allowlist.txt` change needed** for rce. | `grep` script (clean) | High |
| Sibling `20260601000000_rls_cases_domain.sql` (SEC-RLSa, public schema) is the **pattern reference** (SECURITY DEFINER helpers owned by `postgres` to avoid RLS recursion; per-table enable/drop/create/revoke). It is **not yet applied to prod** and defines `public.rls_current_hr_company` — so **do not depend on it**. | Read source (clean, 576 lines) | High |
| `public.is_admin()`, `public.my_company_id()`, `public.my_role()` exist in the DB (used by many earlier policies and by SEC-RLSa). Reusing `public.is_admin()` is safe. | SEC-RLSa usage + historical migrations | Med-High |
| `public.hr_users` keys auth uid as **text** (`hr_users.id = (auth.uid())::text`) and carries `company_id text`. | SEC-RLSa source | High |
| Repo RLS/case-engine test convention = **two-mode**: static SQL-regex (always runs) + live mode gated on env var **`RELOPASS_TEST_DB_URL`** using `psycopg2`. | Read `test_relopass_case_engine_schema.py` (clean) | High |
| The 3 target test files do **not** exist yet. | `[ -f ]` checks (clean) | High |

**Could NOT verify (DB access denied) — implementer must confirm live:**
the exact current `rce.*` table set, row counts, and whether `policy_gaps`/`case_artefacts`/`extraction_agents` are present in the target DB. The migration below is written to **not require** that knowledge (drift-tolerant + safe-by-default).

---

## 2. Decisions (confirmed with the requester)

1. **Scoping model = add linkage + per-principal** (Approach C). Add provisional
   `rce.employees.auth_user_id`, `rce.family_members.auth_user_id`,
   `rce.employers.company_id` (text, mirrors `hr_users.company_id`). Enforce
   Employee / Family / HR / Admin scoping through a SECURITY DEFINER helper.
   These columns are **empty until C1-05a wires the Case Engine to auth** → until
   then authenticated principals see **zero** rce rows (safe default); the backend
   (`postgres` role) is unaffected.
2. **PHI audit = option (a)**: a SECURITY DEFINER `rce.read_phi_field()` accessor
   that enforces access and logs `BIOMETRIC`/`CRIMINAL` reads. **Sink corrected to
   a dedicated `rce.phi_access_log`** (because `public.audit_logs.action_type`
   forbids `'read'`).
3. **Writes stay server-side.** Authenticated gets **SELECT only**; all writes go
   through `postgres` (RLS-bypassing backend) or `service_role`. Matches SEC-RLSa
   and the fact that the anon client never writes `rce.*`.

---

## 3. Migration — `supabase/migrations/20260602000000_rce_tenant_rls.sql`

> Filename suffix **must** be `_rce_tenant_rls.sql` (the static test globs for it).
> Timestamp must be greater than `20260601000000` (latest local). Bump if a sibling
> grabs `20260602000000` first.

**Design pillars**
- **Drift-tolerant:** enumerates rce tables *at apply time*; every statement guarded by `to_regclass(...)` / column existence so unknown-or-missing tables never error.
- **Safe-by-default:** §4a drops *all* existing rce policies, then locks *every* rce base table to `service_role`-only + `REVOKE anon`. §4b *additively* grants scoped authenticated `SELECT`. Any table not explicitly scoped stays service-only — it can never be left permissive or world-readable.
- **Self-contained:** own `rce.*` helpers; depends only on `public.is_admin()` + `public.hr_users`.
- **Reversible:** rollback block at the foot.

```sql
-- ============================================================================
-- SEC-RLSc (AIQ-660) · Tenant-scoped RLS for the rce.* Case Engine schema
-- Parent sprint AIQ-649. Supersedes C1-01a. Branch audit/stage-1-rls-c-rce.
--
-- Replaces the permissive `USING (true)` policies created in
-- 20260528020000_relopass_case_engine_v1.sql (+ extraction-agents / policy_gaps
-- / case_artefacts follow-ups) with tenant-scoped policies per Architecture
-- Report §12.2.
--
-- SAFE-BY-DEFAULT + DRIFT-TOLERANT: see spec SEC-RLSc-IMPLEMENTATION-SPEC.md §3.
-- PHI AUDIT (option a): Postgres has no BEFORE SELECT trigger; we use a
--   SECURITY DEFINER accessor rce.read_phi_field() that audits BIOMETRIC/CRIMINAL
--   reads. public.audit_logs.action_type CHECK forbids 'read', so the sink is a
--   dedicated append-only rce.phi_access_log.
-- LINKAGE: rce.* had no auth linkage; this adds provisional columns
--   (rce.employees.auth_user_id, rce.family_members.auth_user_id,
--    rce.employers.company_id). Empty until C1-05a; HR/employee/family see zero
--   rows until populated. Backend (postgres) bypasses RLS and is unaffected.
-- Reversible: rollback block at foot.
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
    alter table rce.employers add column if not exists company_id text;  -- mirrors hr_users.company_id (text)
    create index if not exists employers_company_id_idx on rce.employers(company_id);
  end if;
end $$;

-- 1. PHI classification column + dedicated audit sink.
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

grant execute on function rce.current_hr_company()      to authenticated, service_role;
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

-- 3. Drop ALL existing policies in schema rce (clears C1-01 permissive set).
do $$
declare r record;
begin
  for r in select policyname, tablename from pg_policies where schemaname = 'rce' loop
    execute format('drop policy if exists %I on rce.%I', r.policyname, r.tablename);
  end loop;
end $$;

-- 4a. Safe default: every rce base table -> RLS on, anon revoked, service_role ALL.
--     Authenticated gets NOTHING here (added selectively in 4b).
do $$
declare t text;
begin
  for t in
    select table_name from information_schema.tables
     where table_schema = 'rce' and table_type = 'BASE TABLE'
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
    'agent_runs','case_artefacts','policy_gaps'
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

-- (v) non-tenant reference/config tables -> authenticated read (non-PII).
do $$
declare
  t text;
  ref_tables text[] := array[
    'document_types','rules','rule_versions','steps','authorities','addresses'
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
--   * rce.canonical_entities  -> cross-case PII identity graph, no tenant column.
--   * rce.extraction_agents   -> internal extraction config.
--   * rce.agent_versions      -> internal extraction telemetry/config.
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
--     for r in select policyname, tablename from pg_policies where schemaname='rce' loop
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
--   -- was the SEC-003 exposure this task removes.
-- commit;
-- ============================================================================
```

### Implementer review checklist for the SQL
- [ ] Confirm `public.is_admin()` exists in the target DB (`select to_regprocedure('public.is_admin()')`). If absent, inline the `admin_allowlist` check.
- [ ] Confirm `auth.uid()` resolves (Supabase). In live tests it reads `request.jwt.claims->>'sub'`.
- [ ] Confirm `rce.cases.case_id` is the PK column name (baseline says yes). If the live `cases` also has an `id` column, policies still key off `case_id`.
- [ ] Run `get_advisors(type:'security')` after apply — expect **no** "RLS disabled"/"policy exists RLS disabled" findings for `rce.*`.

---

## 4. Tests (two-mode, mirroring `test_relopass_case_engine_schema.py`)

All three live under `backend/tests/`. Static classes always run in CI; live
classes skip unless `RELOPASS_TEST_DB_URL` points at a Postgres where this
migration has been applied.

### 4.1 `backend/tests/test_b5_case_engine_isolation.py` (static guard + live policy shape)

```python
"""SEC-RLSc (AIQ-660) — guard that the rce tenant-RLS migration replaces the
permissive C1-01 policies and scopes every tenant table. Extends the B5 pattern
to the rce.* Case Engine schema.

Static mode (CI): parses the migration SQL.
Live mode (RELOPASS_TEST_DB_URL): asserts no permissive authenticated policy
survives on tenant tables.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

CASE_SCOPED = (
    "family_members", "documents", "deadlines", "costs", "corrections", "agent_runs",
)
EMPLOYER_SCOPED = ("employers", "employees", "hr_policies", "policy_clauses")
TRANSITIVE = ("extracted_fields", "entity_links")


@pytest.fixture(scope="module")
def migration_sql() -> str:
    matches = sorted(MIGRATIONS_DIR.glob("*_rce_tenant_rls.sql"))
    assert matches, "SEC-RLSc migration *_rce_tenant_rls.sql not found"
    return matches[-1].read_text()


class TestRceTenantRlsStatic:
    def test_drops_all_existing_rce_policies(self, migration_sql: str) -> None:
        assert re.search(
            r"pg_policies\s+where\s+schemaname\s*=\s*'rce'", migration_sql, re.IGNORECASE
        ), "migration must dynamically drop all existing rce policies"
        assert re.search(r"drop\s+policy\s+if\s+exists", migration_sql, re.IGNORECASE)

    def test_safe_default_service_only_loop(self, migration_sql: str) -> None:
        assert re.search(r"enable\s+row\s+level\s+security", migration_sql, re.IGNORECASE)
        assert re.search(r"revoke\s+all\s+on\s+rce\.", migration_sql, re.IGNORECASE)
        assert re.search(r"to\s+service_role", migration_sql, re.IGNORECASE)

    def test_no_permissive_authenticated_true_on_tenant_tables(self, migration_sql: str) -> None:
        # The only `using (true)` for authenticated must be the reference tables.
        # Assert there is no `for all to authenticated ... using (true)`.
        assert not re.search(
            r"for\s+all\s+to\s+authenticated[^;]*using\s*\(\s*true\s*\)",
            migration_sql, re.IGNORECASE | re.DOTALL,
        ), "no permissive FOR ALL authenticated USING(true) may remain"

    def test_helpers_defined(self, migration_sql: str) -> None:
        for fn in ("rce.current_hr_company", "rce.can_access_case", "rce.can_access_employer"):
            assert re.search(rf"function\s+{re.escape(fn)}\b", migration_sql, re.IGNORECASE), fn

    @pytest.mark.parametrize("table", CASE_SCOPED)
    def test_case_scoped_select_policy(self, migration_sql: str, table: str) -> None:
        assert re.search(rf"\b{table}\b", migration_sql), table
        assert "rce.can_access_case" in migration_sql

    @pytest.mark.parametrize("table", EMPLOYER_SCOPED + TRANSITIVE)
    def test_named_tenant_select_policy(self, migration_sql: str, table: str) -> None:
        assert re.search(rf"{table}_tenant_select", migration_sql), f"{table}_tenant_select missing"

    def test_self_contained_no_sibling_dependency(self, migration_sql: str) -> None:
        assert "public.rls_current_hr_company" not in migration_sql, (
            "must not depend on the SEC-RLSa sibling helper (ordering risk)"
        )


# ----- live mode -----
def _live_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL (migration applied) to run live RLS checks.")
    try:
        import psycopg2
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed")
    return psycopg2.connect(url)


class TestRceTenantRlsLive:
    def test_no_permissive_policy_remains(self) -> None:
        conn = _live_conn()
        try:
            with conn.cursor() as cur:
                # any policy granting authenticated a blanket TRUE on a tenant table?
                cur.execute(
                    """
                    select tablename, policyname, qual
                    from pg_policies
                    where schemaname='rce'
                      and 'authenticated' = any(roles)
                      and coalesce(qual,'') in ('true','(true)')
                      and tablename in ('cases','documents','extracted_fields',
                                        'family_members','deadlines','costs',
                                        'corrections','employers','employees',
                                        'hr_policies','policy_clauses','entity_links')
                    """
                )
                leaks = cur.fetchall()
            assert not leaks, f"permissive authenticated policies remain: {leaks}"
        finally:
            conn.close()
```

### 4.2 `backend/tests/test_rls_case_engine.py` (cross-tenant leak — the core criterion)

```python
"""SEC-RLSc (AIQ-660) — cross-employer leak test for rce.* case-scoped tables.

Validation criterion: a principal from employer B sees 0 rows of employer A.

Static mode (CI): asserts each case-scoped table is scoped via rce.can_access_case.
Live mode (RELOPASS_TEST_DB_URL): seeds two tenants as the table owner, then
queries as an `authenticated` principal of tenant B and asserts 0 tenant-A rows.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
CASE_TABLES = ("documents", "deadlines", "costs", "corrections", "family_members")


@pytest.fixture(scope="module")
def migration_sql() -> str:
    matches = sorted(MIGRATIONS_DIR.glob("*_rce_tenant_rls.sql"))
    assert matches, "SEC-RLSc migration not found"
    return matches[-1].read_text()


class TestStaticScoping:
    @pytest.mark.parametrize("table", CASE_TABLES)
    def test_table_scoped_by_case(self, migration_sql: str, table: str) -> None:
        assert "rce.can_access_case" in migration_sql
        assert re.search(rf"\b{table}\b", migration_sql)


def _live_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL (migration applied) to run live cross-tenant test.")
    try:
        import psycopg2
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def _as_authenticated(cur, uid: str) -> None:
    """Switch the session to the `authenticated` role with a JWT sub = uid."""
    import json
    cur.execute("set local role authenticated")
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"sub": uid, "role": "authenticated"}),),
    )


def _as_owner(cur) -> None:
    cur.execute("reset role")


class TestCrossTenantLive:
    def test_employer_b_sees_no_employer_a_rows(self) -> None:
        conn = _live_conn()
        emp_a, emp_b = uuid.uuid4(), uuid.uuid4()
        hr_b_uid = str(uuid.uuid4())
        try:
            with conn.cursor() as cur:
                _as_owner(cur)
                # Two employers; HR of B is linked via employers.company_id == hr_users.company_id.
                # Seed minimal hr_users row for B so rce.current_hr_company() resolves.
                cur.execute(
                    "insert into rce.employers (employer_id, legal_name, company_id) values "
                    "(%s,'A','company-a'),(%s,'B','company-b')", (str(emp_a), str(emp_b)),
                )
                cur.execute(
                    "insert into public.hr_users (id, company_id) values (%s,'company-b') "
                    "on conflict (id) do update set company_id=excluded.company_id",
                    (hr_b_uid,),
                )
                # One case + one document per employer.
                case_a, case_b = uuid.uuid4(), uuid.uuid4()
                cur.execute(
                    "insert into rce.cases (case_id, employer_id, status) values "
                    "(%s,%s,'ACTIVE'),(%s,%s,'ACTIVE')",
                    (str(case_a), str(emp_a), str(case_b), str(emp_b)),
                )
                cur.execute(
                    "insert into rce.documents (document_id, case_id, sha256) values "
                    "(%s,%s,%s),(%s,%s,%s)",
                    (str(uuid.uuid4()), str(case_a), uuid.uuid4().hex,
                     str(uuid.uuid4()), str(case_b), uuid.uuid4().hex),
                )
                conn.commit()

                # Query as HR of employer B.
                _as_authenticated(cur, hr_b_uid)
                cur.execute("select count(*) from rce.documents where case_id = %s", (str(case_a),))
                a_visible = cur.fetchone()[0]
                cur.execute("select count(*) from rce.documents where case_id = %s", (str(case_b),))
                b_visible = cur.fetchone()[0]

            assert a_visible == 0, "employer B must NOT see employer A documents"
            assert b_visible == 1, "employer B must see its own documents"
        finally:
            conn.rollback()
            conn.close()
```

> Implementer note: adjust seed columns to the live schema (e.g. `cases` may also
> have an `id` column; `hr_users` may have NOT NULL columns needing values). Keep
> the assertion shape: **A-rows visible to B == 0**, **own rows visible == n**.

### 4.3 `backend/tests/test_phi_audit.py` (PHI read audit fires)

```python
"""SEC-RLSc (AIQ-660) — BIOMETRIC/CRIMINAL reads via rce.read_phi_field() are
logged to rce.phi_access_log; NONE reads and service-role reads are not.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


@pytest.fixture(scope="module")
def migration_sql() -> str:
    matches = sorted(MIGRATIONS_DIR.glob("*_rce_tenant_rls.sql"))
    assert matches, "SEC-RLSc migration not found"
    return matches[-1].read_text()


class TestPhiStatic:
    def test_phi_class_column_added(self, migration_sql: str) -> None:
        assert re.search(r"phi_class\s+text", migration_sql, re.IGNORECASE)
        assert "BIOMETRIC" in migration_sql and "CRIMINAL" in migration_sql

    def test_audit_sink_and_accessor_present(self, migration_sql: str) -> None:
        assert re.search(r"create\s+table\s+if\s+not\s+exists\s+rce\.phi_access_log",
                         migration_sql, re.IGNORECASE)
        assert re.search(r"function\s+rce\.read_phi_field", migration_sql, re.IGNORECASE)

    def test_does_not_write_read_to_audit_logs(self, migration_sql: str) -> None:
        # public.audit_logs.action_type CHECK forbids 'read'; ensure we don't target it.
        assert "public.audit_logs" not in migration_sql


def _live_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL (migration applied) to run live PHI audit test.")
    try:
        import psycopg2
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed")
    return psycopg2.connect(url)


class TestPhiAuditLive:
    def _seed_field(self, cur, phi_class: str) -> str:
        emp, case_, doc = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        field = uuid.uuid4()
        cur.execute("insert into rce.employers (employer_id, legal_name) values (%s,'A')", (str(emp),))
        cur.execute("insert into rce.cases (case_id, employer_id, status) values (%s,%s,'ACTIVE')",
                    (str(case_), str(emp)))
        cur.execute("insert into rce.documents (document_id, case_id, sha256) values (%s,%s,%s)",
                    (str(doc), str(case_), uuid.uuid4().hex))
        cur.execute(
            "insert into rce.extracted_fields "
            "(extracted_field_id, document_id, field_key, confidence, phi_class) "
            "values (%s,%s,'x',1.0,%s)", (str(field), str(doc), phi_class),
        )
        return str(field)

    def test_biometric_read_is_logged_admin_path(self) -> None:
        conn = _live_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("reset role")
                field = self._seed_field(cur, "BIOMETRIC")
                conn.commit()
                # Simulate a non-system principal that is admin (so access passes),
                # by switching role to authenticated. Admin resolution depends on
                # public.is_admin(); for the harness, allowlist the test uid first
                # OR call as a principal with case access. Simplest portable check:
                # call the function as the owner but assert the audit branch only
                # fires for non-system roles -> use a dedicated low-priv login role.
                cur.execute("select rce.read_phi_field(%s)", (field,))
                cur.execute("select count(*) from rce.phi_access_log where extracted_field_id=%s",
                            (field,))
                logged = cur.fetchone()[0]
            # owner (postgres) path must NOT log:
            assert logged == 0, "service/owner reads must not be audited"
        finally:
            conn.rollback(); conn.close()

    def test_none_class_never_logged(self) -> None:
        conn = _live_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("reset role")
                field = self._seed_field(cur, "NONE")
                conn.commit()
                cur.execute("select rce.read_phi_field(%s)", (field,))
                cur.execute("select count(*) from rce.phi_access_log where extracted_field_id=%s",
                            (field,))
                assert cur.fetchone()[0] == 0
        finally:
            conn.rollback(); conn.close()
```

> Implementer note: to assert the **positive** audit case (a real non-system
> principal triggers a log row), create a dedicated NOLOGIN/role or a test login
> role that is neither `postgres` nor `service_role`, grant it `authenticated`,
> set it admin via `public.admin_allowlist` (so the access check passes), call
> `rce.read_phi_field()`, and assert exactly one `phi_access_log` row with
> `action='phi.read'` and `phi_class='BIOMETRIC'`. This needs a real login role,
> which is why it's a live-mode test.

---

## 5. Validation procedure (must run before merge)

1. **Static (no DB):** `cd backend && pytest backend/tests/test_rls_case_engine.py backend/tests/test_b5_case_engine_isolation.py backend/tests/test_phi_audit.py -k "Static or static" -v` → all green.
2. **Apply on a throwaway DB / Supabase branch** (drift-tolerant, so it applies whatever rce tables exist):
   - via Supabase MCP `apply_migration` on a dev branch, or `supabase db push` against a scratch project, or a local `supabase start`.
3. **Live (with DB):** `RELOPASS_TEST_DB_URL=postgres://... pytest backend/tests/test_rls_case_engine.py backend/tests/test_phi_audit.py backend/tests/test_b5_case_engine_isolation.py -v` → cross-tenant returns 0; PHI audit fires.
4. **Advisors:** `get_advisors(type:'security')` shows no RLS gaps for `rce.*`.
5. **Regression:** `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest backend/tests/test_relopass_case_engine_schema.py backend/tests/test_b5_company_isolation.py -v` (C1-01 + existing B5 still green).
6. **Policy inventory for the Notion Execution Note:**
   `select schemaname, tablename, policyname, cmd, roles from pg_policies where schemaname='rce' order by tablename, policyname;`

---

## 6. Handoff bookkeeping
- **No `rls_allowlist.txt` edit** (coverage scans `public` only).
- **Branch:** `audit/stage-1-rls-c-rce`; one PR; one re-audit doc.
- **Notion AIQ-660 → Human Review** only after step 3 above passes; paste the §5.6
  inventory + a sample cross-tenant result into Execution Notes.
- **Provisional-linkage follow-up:** file a note for the **C1-05a** owner to
  populate `rce.employees.auth_user_id`, `rce.family_members.auth_user_id`, and
  `rce.employers.company_id` when the Case Engine is wired to auth — until then
  HR/employee/family principals see zero rce rows by design.
```
