-- AIQ-649 / SEC (SEC-002 + C1-01a + AUDIT-A3-followup) — close residual
-- cross-tenant read leaks left after the SEC-RLS sprint.
--
-- The sprint gave every public + rce table an RLS policy (allowlist drained to
-- 0). But "has a policy" ≠ "tenant-scoped": a permissive `TO authenticated
-- USING (true)` SELECT policy on a table that carries a tenant column lets any
-- logged-in user (the frontend's Supabase anon key + a user JWT resolves to
-- role `authenticated`) read every tenant's rows. REVOKE FROM anon does not
-- close this — authenticated ≠ anon.
--
-- A systematic scan of permissive-read tables carrying a tenant column found
-- exactly five, fixed here. All other permissive-read tables are global
-- reference/catalog data (countries, requirements, knowledge base, supplier
-- catalog, rce rule definitions) and are intentionally world/authenticated
-- readable.
--
-- Uses the helpers established by the cases-domain sprint migration
-- (20260601000000): rls_can_access_assignment(text), my_company_id(), is_admin().
-- All five tables are empty in prod at apply time (pre-launch) — this closes a
-- latent leak before real data lands.

begin;

-- 1) form_prefill_instances — prefilled form field values (PII) keyed by
--    assignment_id (text, = case_assignments.id). Scope to the assignment's
--    owner: the employee, same-company HR, or an admin.
drop policy if exists form_prefill_instances_select_authenticated on public.form_prefill_instances;
create policy form_prefill_instances_select_scoped
  on public.form_prefill_instances
  for select to authenticated
  using (public.rls_can_access_assignment(assignment_id));

-- 2) canonical_policy_* family — company_id is text (varchar). Preserve global
--    (NULL company_id) reference rows for all authenticated users; scope
--    per-company rows to that company or an admin. my_company_id() is uuid →
--    cast to text for the comparison.
drop policy if exists canonical_policy_documents_auth_read on public.canonical_policy_documents;
create policy canonical_policy_documents_read_scoped
  on public.canonical_policy_documents
  for select to authenticated
  using (company_id is null or company_id = public.my_company_id()::text or public.is_admin());

drop policy if exists canonical_policy_document_chunks_auth_read on public.canonical_policy_document_chunks;
create policy canonical_policy_document_chunks_read_scoped
  on public.canonical_policy_document_chunks
  for select to authenticated
  using (company_id is null or company_id = public.my_company_id()::text or public.is_admin());

drop policy if exists canonical_policy_facts_auth_read on public.canonical_policy_facts;
create policy canonical_policy_facts_read_scoped
  on public.canonical_policy_facts
  for select to authenticated
  using (company_id is null or company_id = public.my_company_id()::text or public.is_admin());

drop policy if exists canonical_policy_fact_validation_errors_auth_read on public.canonical_policy_fact_validation_errors;
create policy canonical_policy_fact_validation_errors_read_scoped
  on public.canonical_policy_fact_validation_errors
  for select to authenticated
  using (company_id is null or company_id = public.my_company_id()::text or public.is_admin());

commit;
