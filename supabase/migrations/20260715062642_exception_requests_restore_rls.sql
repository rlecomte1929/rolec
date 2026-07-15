-- Restore RLS on public.exception_requests.
--
-- 20260923000000_fix_exception_requests_types recreated this table to reconcile its
-- SQLite-shaped column types with the migration. Recreating it silently dropped the RLS
-- that 20260913010000_exception_requests_enable_rls had added: prod now has
-- relrowsecurity = false and ZERO policies, and CI's RLS coverage gate fails on it.
--
-- Scope of the exposure: NONE, as it happens. Neither `anon` nor `authenticated` holds any
-- grant on this table (only postgres + service_role do), so PostgREST cannot reach it with
-- the anon key that ships in the frontend bundle. This is a defense-in-depth regression,
-- not an open door — but the repo's hard rule is RLS + a policy + no anon grant on every
-- public table, precisely so that a future GRANT can't quietly turn it into one. SEC-002
-- is what that rule exists to prevent.
--
-- This restores exactly what 20260913010000 established. Idempotent.

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

-- Defense-in-depth: the anon key is public (it ships in the frontend bundle).
REVOKE ALL ON public.exception_requests FROM anon;
