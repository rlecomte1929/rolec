-- AIQ-1410 follow-up — apply the reviewed SAFE SUBSET of the Oct-30 2026 Data-API grants.
--
-- From 2026-10-30 Supabase enforces that a table needs an explicit grant to anon/authenticated
-- before the Data API (PostgREST + Realtime) can reach it; the old auto-grant is removed. These
-- six tables are live frontend Data-API dependencies that today have ZERO grants and would
-- silently lose access on Oct-30. Each has RLS ENABLED with row-scoping policies verified against
-- prod on 2026-07-05 (see docs/security/AIQ-1410_data_api_grants_audit.md), so GRANT SELECT is
-- additive and stays gated by RLS — it preserves current behaviour, it does not widen row access.
-- Grants go to `authenticated` only; none of these need anonymous (logged-out) access.
-- Idempotent: re-running GRANT is a no-op.

grant select on public.case_forms               to authenticated;  -- realtime (in publication) + RLS: case_id -> cases(employee/company)
grant select on public.profiles                 to authenticated;  -- RLS: own / hr-company-scoped / admin; AuthProvider read
grant select on public.notification_preferences to authenticated;  -- RLS: user_id = auth.uid()
grant select on public.policy_documents         to authenticated;  -- RLS: hr_company_ids() OR is_admin()
grant select on public.daily_summaries          to authenticated;  -- RLS: admin-only
grant select on public.pet_import_rules         to authenticated;  -- public reference data (non-PII), RLS USING(true)

-- EXCLUDED — each needs a prior fix before it can be safely granted (see the audit doc):
--   notifications  : only an is_admin() policy exists; a grant alone still delivers nothing to
--                    normal users. Needs a per-user SELECT policy first.
--   provider_tasks : NOT in the supabase_realtime publication -> its realtime sub already no-ops;
--                    a grant alone won't restore it (separate latent bug).
--   supplier_stats : RLS is OFF -> a grant would expose every row to any logged-in user. Enable
--                    RLS + add policies first.
