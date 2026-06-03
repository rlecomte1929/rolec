# Execution Prompt — SEC-RLSb · RLS for Policy / HR Domain

**Notion:** AIQ-659 — `https://www.notion.so/370887c64d488137af03f963e0ad82be`
**Parent sprint:** AIQ-649. Parallel with SEC-RLSa/c/d/e; SEC-RLSf closes.
**Priority:** **P0** · **Complexity:** High · **Branch:** `audit/stage-1-rls-b-policy-hr`

## Role
Backend security engineer. You ship `company_id`-scoped policies on HR/policy tables. These are the rows HR owns and only their company should see.

## Read first
- `supabase/migrations/20260325000000_case_milestones.sql` — canonical pattern.
- `supabase/rls_allowlist.txt` — full list.
- `scripts/check_rls_coverage.py` — CI gate.
- `backend/main.py` and `backend/app/routers/policy_*.py` for the `_get_hr_company_id` resolution pattern.

## Tables in scope (verify against rls_allowlist.txt)
HR-owned, company_id-scoped:
- `hr_policies`
- `company_policies`, `company_policy_assistant_bindings`, `company_preferred_suppliers`, `company_vendor_selections`
- All `policy_*` tables: `policy_assignment_type_applicability`, `policy_assistant_answer_audits`, `policy_benefit_jurisdiction_overrides`, `policy_benefit_rule_hr_override_audit`, `policy_benefit_rule_hr_overrides`, `policy_benefit_rules`, `policy_config_benefits`, `policy_config_versions`, `policy_configs`, `policy_document_chunks`, `policy_document_clauses`, `policy_documents`, `policy_evidence_requirements`, `policy_exclusions`, `policy_extraction_locks`, `policy_facts`, `policy_family_status_applicability`, `policy_knowledge_snapshots`, `policy_rule_conditions`, `policy_rules`, `policy_source_links`, `policy_tier_overrides`, `policy_versions`
- `canonical_policy_*` family: `canonical_policy_document_chunks`, `canonical_policy_documents`, `canonical_policy_fact_validation_errors`, `canonical_policy_facts`
- `compliance_actions`, `compliance_reports`
- `collaboration_*` if company-scoped (verify schema; otherwise → SEC-RLSe)

## Migration shape
`supabase/migrations/<NEW-TS>_rls_policy_hr_domain.sql` — single migration. Timestamp strictly after `20260531000000`.

Pattern for company_id-scoped tables:
```sql
ALTER TABLE public.<table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table>_hr_select" ON public.<table>
  FOR SELECT TO authenticated
  USING (
    company_id IN (
      SELECT company_id FROM public.hr_users WHERE auth_user_id = auth.uid()
    )
  );

CREATE POLICY "<table>_hr_write" ON public.<table>
  FOR ALL TO authenticated
  USING (
    company_id IN (
      SELECT company_id FROM public.hr_users WHERE auth_user_id = auth.uid()
    )
  ) WITH CHECK (
    company_id IN (
      SELECT company_id FROM public.hr_users WHERE auth_user_id = auth.uid()
    )
  );

REVOKE ALL ON public.<table> FROM anon;
```

For tables that don't have `company_id` directly: join through the parent (e.g. `policy_document_chunks → policy_documents.company_id`). Document the join in a SQL comment above each `CREATE POLICY`.

For `canonical_policy_*` (shared knowledge graph, **not** per-company): SELECT for any authenticated user; mutations for admin role only. Document the rationale in the migration header.

## Allowlist update
Remove every triaged table from `supabase/rls_allowlist.txt`.

## Tests
`backend/tests/integration/test_rls_policy_hr_domain.py`:
1. Anon → empty / 401 on every table.
2. HR Admin Org 1 → reads only Org 1's policy artifacts; cannot read Org 2's.
3. HR Admin Org 2 → reads only Org 2's; cannot read Org 1's.
4. Employee A (not HR) → empty result on company-scoped tables (employees don't see HR-only data directly here).
5. Service-role bypass intact (used by backend extract pipelines).

Hit PostgREST directly via httpx with the anon key + per-persona JWT.

## HR Command Center smoke test
After the migration, manually exercise the HR Command Center (`/hr/*` routes). Every panel that previously rendered policy/HR data must still render. If anything 403s or shows empty unexpectedly, the policy is too restrictive — fix it before merging.

## Validation
```bash
python scripts/check_rls_coverage.py --allowlist supabase/rls_allowlist.txt   # exits 0
cd backend && pytest backend/tests/integration/test_rls_policy_hr_domain.py -v
# Manual: load /hr/command-center as a real HR user; confirm all data renders.
```

## Constraints
- Do not touch cases-domain (SEC-RLSa), catalog (SEC-RLSd), or audit-only (SEC-RLSe) tables.
- `canonical_policy_*` are shared — do not company-scope them.
- `policy_extraction_locks` is server-internal — likely belongs to SEC-RLSe; check the schema and triage accordingly.
- Migration reversible — rollback block in trailing comment.

## Definition of done
- Single migration applies cleanly.
- All listed tables in `pg_policies`.
- Allowlist count drops by N (state in Execution Notes).
- HR Command Center smoke test green.
- Integration tests pass.
- `check_rls_coverage.py` green.
- Notion AIQ-659 → Human Review with migration filename + count delta + HR smoke output.
- Commit per CLAUDE.md Build Hygiene rules.
