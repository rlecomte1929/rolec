-- Enable RLS on public.exception_requests — the one policy-less public table failing the
-- RLS-coverage gate (allowlist is drained to 0). A prior enable-RLS migration was recorded
-- in the ledger but never took effect on prod, so RLS was still OFF.
--
-- This LOCKS THE TABLE DOWN (service-role writes + admin reads only). It intentionally does
-- NOT attempt tenant-scoped employee/HR access — the table is the drifted/dead AIQ-1587
-- redesign shape (its live endpoints already 500), and restoring that functionality is a
-- separate task. The goal here is defense-in-depth + satisfying the hard RLS gate:
-- RLS enabled + at least one policy + REVOKE ALL FROM anon.
--
-- Idempotent (safe to re-run / Preview replay).

ALTER TABLE public.exception_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS exception_requests_service_all ON public.exception_requests;
CREATE POLICY exception_requests_service_all ON public.exception_requests
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS exception_requests_admin_read ON public.exception_requests;
CREATE POLICY exception_requests_admin_read ON public.exception_requests
  FOR SELECT TO authenticated USING (public.is_admin());

REVOKE ALL ON public.exception_requests FROM anon;
