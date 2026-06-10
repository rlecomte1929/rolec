-- SEC-RLSg (AIQ-949) · Admin-only RLS on ai_spend_requests + rp_debug_kv
--
-- Recon (2026-06-10) found these two internal-ops tables had PERMISSIVE
-- `USING (true)` policies AND a live `authenticated` grant — so any logged-in
-- user could read ai_spend_requests (AI-spend governance) and read/insert/update
-- rp_debug_kv (debug key-value) via PostgREST. (anon had matching USING(true)
-- policies but NO table grant, so anon couldn't reach them — still dropped here
-- so no permissive policy lingers.) Neither table carries a tenant column; they
-- are internal ops/debug data that only admins (and the service role, which
-- bypasses RLS) should touch.
--
-- Fix: drop every permissive policy and replace with admin-only ones using the
-- existing public.is_admin() helper. The `authenticated` grants are KEPT so an
-- admin (authenticated role) can still read via PostgREST; the policy gates the
-- rows. Backend writes go through the service role and bypass RLS, so dropping
-- the authenticated write policies does not affect the app.
--
-- Idempotent: DROP POLICY IF EXISTS + CREATE. RLS already enabled on both tables.
-- Follows the AIQ-649 pattern (20260617010000_rls_permissive_read_tenant_scope.sql).

-- ── public.ai_spend_requests ────────────────────────────────────────────────
DROP POLICY IF EXISTS anon_read_spend_requests          ON public.ai_spend_requests;
DROP POLICY IF EXISTS authenticated_read_spend_requests ON public.ai_spend_requests;

CREATE POLICY ai_spend_requests_admin_read
  ON public.ai_spend_requests
  FOR SELECT TO authenticated
  USING (public.is_admin());

-- ── public.rp_debug_kv ──────────────────────────────────────────────────────
DROP POLICY IF EXISTS anon_read_debug_kv          ON public.rp_debug_kv;
DROP POLICY IF EXISTS authenticated_read_debug_kv ON public.rp_debug_kv;
DROP POLICY IF EXISTS authenticated_update_debug_kv ON public.rp_debug_kv;
DROP POLICY IF EXISTS authenticated_write_debug_kv  ON public.rp_debug_kv;

CREATE POLICY rp_debug_kv_admin_read
  ON public.rp_debug_kv
  FOR SELECT TO authenticated
  USING (public.is_admin());

CREATE POLICY rp_debug_kv_admin_insert
  ON public.rp_debug_kv
  FOR INSERT TO authenticated
  WITH CHECK (public.is_admin());

CREATE POLICY rp_debug_kv_admin_update
  ON public.rp_debug_kv
  FOR UPDATE TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());
