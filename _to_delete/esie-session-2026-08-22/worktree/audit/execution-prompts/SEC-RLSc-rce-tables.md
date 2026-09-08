# Execution Prompt — SEC-RLSc · RLS for `rce.*` Case Engine Tables

**Notion:** AIQ-660 — `https://www.notion.so/370887c64d4881e89121e0ef74b7a950`
**Parent sprint:** AIQ-649. Parallel with SEC-RLSa/b/d/e; SEC-RLSf closes.
**Priority:** **P0** · **Complexity:** High · **Branch:** `audit/stage-1-rls-c-rce`

> This subtask **supersedes** the prior `C1-01a` standalone task. If you're carrying that prompt forward, drop it — this is the canonical version.

## Role
Backend security engineer. You replace C1-01's permissive `USING (true)` policies on every `rce.*` table with tenant-scoped policies per Architecture Report §12.2.

## Read first
- `supabase/migrations/20260528020000_relopass_case_engine_v1.sql` — current permissive baseline you're replacing. Header comment says: *"Policies are permissive in this migration; C1-01a replaces them with tenant-scoped policies."* That's now this task.
- `supabase/migrations/20260529100000_rce_extraction_agents.sql` — `rce.extraction_agents`, `rce.agent_versions`.
- `supabase/migrations/20260531000000_agent_runs.sql` — latest migration; new timestamp must be greater.
- Architecture Report §12.2 (authentication & scoping).

## Tables in scope (rce.* schema — NOT public)
Every table in the `rce` schema, including but not limited to:
- `rce.cases`, `rce.employees`, `rce.family_members`, `rce.canonical_entities`, `rce.entity_links`
- `rce.documents`, `rce.document_types`, `rce.extracted_fields`, `rce.corrections`, `rce.contradictions`
- `rce.rule_versions`, `rce.rules`, `rce.rule_citations` (if shipped — verify), `rce.rule_change_proposals` (if shipped — verify)
- `rce.steps`, `rce.deadlines`, `rce.costs`, `rce.hr_policies`, `rce.policy_clauses`
- `rce.extraction_agents`, `rce.agent_versions`, `rce.case_artefacts`, `rce.policy_gaps`
- `rce.agent_runs` (if in the rce schema — confirm; if public, → SEC-RLSe)

Confirm the full set with: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'rce' ORDER BY 1;`

## Principal model (Architecture Report §12.2)
Three principals:
- **HR Operator** — employer-scoped via JWT claim:
  ```sql
  USING (
    case_id IN (
      SELECT case_id FROM rce.cases
       WHERE employer_id = (current_setting('request.jwt.claims', true)::json->>'employer_id')::uuid
    )
  )
  ```
  Or, if `hr_users` is the source of truth for employer_id (verify in `backend/services/auth.py`):
  ```sql
  USING (
    case_id IN (
      SELECT case_id FROM rce.cases c
       WHERE c.employer_id IN (
         SELECT employer_id FROM public.hr_users WHERE auth_user_id = auth.uid()
       )
    )
  )
  ```
- **Employee** — own case only:
  ```sql
  USING (
    case_id IN (
      SELECT case_id FROM rce.cases
       WHERE primary_employee_id = (SELECT employee_id FROM rce.employees WHERE auth_user_id = auth.uid())
    )
  )
  ```
- **Family Member** — sub-scope: same case_id scoping, plus filter on `family_member_id` matching the auth subject.

## Migration shape
`supabase/migrations/<NEW-TS>_rce_tenant_rls.sql`:

```sql
-- 1. Drop the permissive policies from C1-01.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT schemaname, tablename, policyname
            FROM pg_policies WHERE schemaname='rce'
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON rce.%I', r.policyname, r.tablename);
  END LOOP;
END $$;

-- 2. Per-table tenant-scoped policies.
-- (For each rce.<table>, apply the HR Operator + Employee policies above,
--  joining through case_id to rce.cases.)

-- 3. PHI audit trigger on rce.extracted_fields.
CREATE OR REPLACE FUNCTION rce.fn_phi_read_audit()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.phi_class IN ('BIOMETRIC','CRIMINAL')
     AND current_user NOT IN ('postgres','service_role')
  THEN
    INSERT INTO public.audit_events (principal_id, action, target_table, target_id, occurred_at)
    VALUES (auth.uid(), 'phi.read', 'rce.extracted_fields', NEW.field_id::text, now());
  END IF;
  RETURN NEW;
END $$;

-- Triggers on SELECT aren't supported in Postgres; implement via a view + audit
-- on the underlying query, OR via the app layer (FastAPI dep that wraps reads
-- of phi_class-flagged rows). Pick whichever you can make watertight; document
-- the choice in the migration header.
```

> **Open design call:** Postgres doesn't support `BEFORE SELECT` triggers. You have two options for the BIOMETRIC/CRIMINAL audit:
> (a) wrap reads in a SECURITY DEFINER function called by the app layer (`SELECT rce.read_phi_field(...)`), which inserts into `audit_events` then returns the row;
> (b) audit at the FastAPI router level in `backend/app/routers/` whenever a phi_class-flagged field is returned.
> Pick one, justify in the migration header. Don't ship a fake trigger.

## Allowlist update
`rce.*` tables aren't in the **public**-schema allowlist, so `rls_allowlist.txt` shouldn't need editing here. If `check_rls_coverage.py` scans schemas beyond `public`, update it or document scope.

## Tests
- `backend/tests/test_rls_case_engine.py` — cross-employer leak test for every `rce.*` table with `case_id`.
- `backend/tests/test_b5_case_engine_isolation.py` — extends the B5 pattern to `rce.*`.
- `backend/tests/test_phi_audit.py` — reading a BIOMETRIC/CRIMINAL field by non-system principal writes to `audit_events`.

## Constraints
- Do not break existing B5 isolation on `relocation_cases` / `hr_users`.
- Tables write-only from the backend (server-role-only) may keep permissive policies — flag in migration header which ones and why.
- Migration reversible — rollback block in trailing comment.

## Test commands
```
cd backend && pytest backend/tests/test_rls_case_engine.py backend/tests/test_b5_case_engine_isolation.py backend/tests/test_phi_audit.py -v
psql "$DATABASE_URL" -c "SELECT schemaname, tablename, policyname FROM pg_policies WHERE schemaname='rce' ORDER BY tablename;"
```

## Definition of done
- Permissive C1-01 policies replaced; every `rce.*` table has tenant-scoped policies.
- PHI audit decision documented + implemented (option a or b above).
- 3 test files green.
- Notion AIQ-660 → Human Review with the policy inventory query output + sample cross-tenant test in Execution Notes.
- Commit per CLAUDE.md Build Hygiene rules.
