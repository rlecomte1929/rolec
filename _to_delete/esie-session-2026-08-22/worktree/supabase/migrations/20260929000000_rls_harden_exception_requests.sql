-- Harden public.exception_requests with RLS — it was created by the AIQ-1570
-- over-cap exception flow AFTER the 2026-06-05 defense-in-depth sweep
-- (20260605300000_rls_defense_in_depth_service_role.sql) and so was never given
-- a policy. scripts/check_rls_coverage.py flags it as the one policy-less table
-- in `public`, failing CI on every migration PR until this lands.
--
-- The table is server-managed only: the backend reaches it via the service role
-- (backend/app/routers/exception_requests.py), and the frontend reads it solely
-- through GET /api/cases/{id}/exceptions — never via the Supabase anon client
-- (anon already lacks SELECT). So the canonical server-role-only pattern applies,
-- identical to the 37 tables hardened in the defense-in-depth migration:
-- enable RLS, add an explicit service_role ALL policy (service_role bypasses RLS,
-- so this is documentation + belt-and-suspenders), and REVOKE anon. anon /
-- authenticated get no permissive policy, so they are implicitly denied.
--
-- Replay-safe: ENABLE RLS is idempotent, DROP POLICY IF EXISTS precedes CREATE,
-- and REVOKE is a no-op when already revoked.
ALTER TABLE public.exception_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS exception_requests_service_role_all ON public.exception_requests;
CREATE POLICY exception_requests_service_role_all ON public.exception_requests
  FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON public.exception_requests FROM anon;
