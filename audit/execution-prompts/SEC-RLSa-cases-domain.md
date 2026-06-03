# Execution Prompt — SEC-RLSa · RLS for Cases Domain

**Notion:** AIQ-658 — `https://www.notion.so/370887c64d4881cd9359cdf4d92ac48d`
**Parent sprint:** AIQ-649 (SEC · Complete RLS coverage). Runs in parallel with SEC-RLSb/c/d/e; SEC-RLSf closes.
**Priority:** **P0** · **Complexity:** High · **Branch:** `audit/stage-1-rls-a-cases`

## Role
Backend security engineer + Supabase RLS specialist. You ship tenant-scoped policies for every `public.case_*` and assignment-scoped table on the allowlist. Don't break the legacy B5 fix or `case_milestones` (already scoped).

## Read first
- `supabase/migrations/20260325000000_case_milestones.sql` — **canonical pattern**. Match shape, naming, and `REVOKE FROM anon`.
- `supabase/rls_allowlist.txt` — full list (113 entries on 2026-05-30).
- `scripts/check_rls_coverage.py` — CI script that gates this. (Note: the Notion task body says `scripts/rls_coverage_check.py`; the actual path is `scripts/check_rls_coverage.py` — use the real one.)
- `backend/main.py` and `backend/app/routers/cases.py` for the JWT → employer_id / employee_id resolution patterns currently in use.

## Tables in scope (verify against `rls_allowlist.txt` before editing)
Cases + assignment-scoped tenant tables:
- `case_assignment_id`, `case_documents`, `case_evidence`, `case_feedback`, `case_participants`, `case_people`
- `case_readiness`, `case_readiness_checklist_state`, `case_readiness_milestone_state`
- `case_requirement_evaluations`, `case_requirements_snapshots`
- `assignment_audit_log`, `assignment_mobility_links`, `assignment_policy_service_comparisons`
- `relocation_artifacts`, `relocation_runs`, `relocation_sources`
- `resolved_assignment_policies`, `resolved_assignment_policy_benefits`, `resolved_assignment_policy_exclusions`
- `profile_state`, `eligibility_overrides`
- `readiness_templates`, `readiness_template_checklist_items`, `readiness_template_milestones`
- `wizard_cases`, `answers`, `employee_answers` (verify; may belong with policy/HR instead — triage)

For each table:
1. Identify the join path to a `case_id` or `assignment_id` (one hop max; if it's deeper, document why and bump to SEC-RLSb if HR-owned).
2. Apply tenant-scoped policies per the case_milestones pattern.

## Migration shape
`supabase/migrations/<NEW-TS>_rls_cases_domain.sql` — single migration per domain. Timestamp must be strictly greater than the latest in tree (currently `20260531000000_agent_runs.sql`).

For each table (template — adapt the USING expression to the actual schema):
```sql
ALTER TABLE public.<table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table>_employee_select" ON public.<table>
  FOR SELECT TO authenticated
  USING (
    case_id IN (
      SELECT id FROM public.cases
       WHERE employee_id = (SELECT id FROM public.employees WHERE auth_user_id = auth.uid())
    )
  );

CREATE POLICY "<table>_hr_select" ON public.<table>
  FOR SELECT TO authenticated
  USING (
    case_id IN (
      SELECT id FROM public.cases
       WHERE company_id IN (
         SELECT company_id FROM public.hr_users WHERE auth_user_id = auth.uid()
       )
    )
  );

-- Write policies: same scoping; admins / service_role bypass.
CREATE POLICY "<table>_hr_write" ON public.<table>
  FOR ALL TO authenticated
  USING (...) WITH CHECK (...);

REVOKE ALL ON public.<table> FROM anon;
```

Templates (`readiness_templates*`) are not tenant-scoped — they're public-read for any authenticated user, write for admin role only.

## Allowlist update
For every table you give a policy: **remove its line** from `supabase/rls_allowlist.txt`. The list should drain. Keep `# section header` comments.

## Tests
`backend/tests/integration/test_rls_cases_domain.py` — five-persona × every protected table:
1. Anon (no JWT) → empty / 401 on every table.
2. Employee A → own case rows only.
3. Employee B → own case rows only; cannot see A's.
4. HR Admin Org 1 → all Org 1 case rows; cannot see Org 2's.
5. HR Admin Org 2 → all Org 2 case rows; cannot see Org 1's.

Hit PostgREST directly via httpx using the anon key + per-persona JWT (not FastAPI).

## Validation
```bash
python scripts/check_rls_coverage.py --allowlist supabase/rls_allowlist.txt   # exits 0
cd backend && pytest backend/tests/integration/test_rls_cases_domain.py -v
# Live exploit probe (per table):
curl "https://<project>.supabase.co/rest/v1/case_documents?select=*" -H "apikey: <anon>"
# Expected: [] or 401
```

## Constraints
- Do **not** touch tables that belong to other RLS subtasks (policy/HR → b, rce.* → c, catalog → d, audit-only → e).
- Do **not** break the existing B5 fix on `relocation_cases` / `hr_users`.
- Migration is reversible: bundle a `DROP POLICY ... ; ALTER TABLE ... DISABLE ROW LEVEL SECURITY;` rollback block in a comment at the end of the file.
- Do not auto-merge — Romain reviews the policy logic.

## Definition of done
- Single migration applies cleanly to staging.
- All cases-domain tables have ≥1 policy in `pg_policies`.
- Allowlist line count drops by N (state the number in Execution Notes).
- All 5 persona × table integration tests pass.
- `check_rls_coverage.py` green.
- Notion AIQ-658 → Human Review with the migration filename + count delta + sample tenant-isolation test output in Execution Notes.
- Commit per CLAUDE.md Build Hygiene rules.
