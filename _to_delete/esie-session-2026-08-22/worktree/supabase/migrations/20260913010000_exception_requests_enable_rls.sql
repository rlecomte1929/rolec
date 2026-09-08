-- Enable RLS on public.exception_requests (ledger reconciliation).
--
-- WHY
-- ---
-- The RLS coverage check flagged exception_requests as having no policy. Investigation:
-- the table exists in prod with RLS *disabled* and zero policies, because the two
-- migrations that create and harden it were never applied —
--   20260503100000_p2_exception_requests.sql          (CREATE TABLE + ENABLE RLS)
--   20260507100000_exception_requests_hardening.sql   (granular policies)
-- — while a LATER migration that alters it (20260519221744_enrich_exception_requests_fields)
-- WAS applied. So the table got created out-of-band, unprotected.
--
-- This was pre-existing drift, surfaced (not caused) by the first migration-touching PR
-- in a while: the RLS gate only runs when supabase/migrations/ changes.
--
-- SAFETY — why enabling RLS here cannot break the backend
-- ------------------------------------------------------
-- Before this change, the ONLY roles that could read the table were `postgres` and
-- `service_role`, and BOTH have rolbypassrls = true — RLS is not evaluated for them.
-- `anon`, `authenticated` and the least-privilege API role `relopass_api` had no SELECT
-- grant at all. So this is pure defense-in-depth: it changes no query's result today, and
-- it means the table is protected if a grant is ever added later.
--
-- WHY NOT the full 20260507100000 policy set
-- ------------------------------------------
-- That migration adds HR/employee policies TO authenticated, subquerying
-- public.case_assignments. Two problems here: (a) `authenticated` has no grant on
-- exception_requests, so those policies are inert; (b) `authenticated` also has no grant on
-- case_assignments, and a policy whose USING clause subqueries an ungranted table raises
-- 42501 rather than filtering — the exact failure mode behind the pets-page 500s. Adding
-- them would be a false-green: policy count satisfied, protection illusory. If the table is
-- ever exposed to authenticated, do it together with the matching grants and a
-- SECURITY DEFINER helper for the case_assignments lookup.
--
-- APPLIED OUT-OF-BAND: DDL run via execute_sql on 2026-07-14 and recorded in
-- supabase_migrations.schema_migrations as version 20260913010000. This file is the
-- reconciling record — it is idempotent and safe to re-run.

BEGIN;

ALTER TABLE public.exception_requests ENABLE ROW LEVEL SECURITY;

-- The FastAPI backend reaches this table with a bypassrls role; the policy makes that
-- explicit and satisfies the "RLS enabled => at least one policy" rule.
DROP POLICY IF EXISTS exception_requests_service_role ON public.exception_requests;
CREATE POLICY exception_requests_service_role
  ON public.exception_requests
  FOR ALL
  TO service_role
  USING (TRUE)
  WITH CHECK (TRUE);

-- Defense-in-depth: the anon key ships in the frontend bundle.
REVOKE ALL ON public.exception_requests FROM anon;

COMMIT;
