-- P2 RLS hardening: public.case_budget_lines (backend-only, RLS was OFF).
--
-- Surfaced by scripts/check_rls_coverage.py once the RLS-coverage CI gate was
-- activated (2026-06-03). Unlike the 37 tables in
-- 20260605300000_rls_defense_in_depth_service_role.sql (RLS on, no policy),
-- this table had RLS fully DISABLED — it landed after the 2026-05-25 allowlist
-- seed and was never hardened.
--
-- Audit (prod nsvefcvpvwwwhuqyuqmp, 2026-06-03): grants are postgres +
-- service_role only — ZERO anon / authenticated grants — so the table is not
-- reachable via the Data API today. The backend reaches it through the
-- service-role/owner connection, which BYPASSES RLS, so enabling RLS + a
-- service-role policy grants no new access and changes no behaviour; it closes
-- the rls_disabled gap and clears the coverage gate.
--
-- Per supabase/rls_allowlist.txt policy ("the list should DRAIN, not GROW; new
-- policy-less tables must be moved to migrations"), this is fixed here rather
-- than allowlisted.
--
-- Replay-safe: to_regclass guard, ENABLE RLS is idempotent, DROP POLICY IF
-- EXISTS before CREATE, REVOKE is a no-op when no grant was present.

DO $$
BEGIN
  IF to_regclass('public.case_budget_lines') IS NULL THEN
    RAISE NOTICE 'skipping missing table public.case_budget_lines';
    RETURN;
  END IF;

  EXECUTE 'ALTER TABLE public.case_budget_lines ENABLE ROW LEVEL SECURITY';

  EXECUTE 'DROP POLICY IF EXISTS case_budget_lines_service_role_all ON public.case_budget_lines';
  EXECUTE 'CREATE POLICY case_budget_lines_service_role_all ON public.case_budget_lines '
       || 'FOR ALL TO service_role USING (true) WITH CHECK (true)';

  EXECUTE 'REVOKE ALL ON public.case_budget_lines FROM anon';
END$$;
