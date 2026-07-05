-- =============================================================================
-- Supplier Catalog GAP 4: HR-write RLS on company_preferred_suppliers
--
-- The table (20260328000000) shipped with only a service_role policy, so the
-- HR preferred-supplier feature works today solely because the backend uses the
-- service-role key and scopes by company_id in Python. This adds the missing
-- authenticated/HR policy (defense-in-depth) using the canonical hr_company_ids()
-- helper — an HR user may read/write only rows for companies they belong to via
-- public.hr_users; admins are carved out via public.is_admin().
--
-- Mirrors the established pattern in 20260601030000_benefit_optimizer.sql.
-- company_id is already text, so no ::text cast is needed.
-- =============================================================================

BEGIN;

ALTER TABLE public.company_preferred_suppliers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_preferred_suppliers_company_scoped ON public.company_preferred_suppliers;
CREATE POLICY company_preferred_suppliers_company_scoped ON public.company_preferred_suppliers
  FOR ALL
  TO authenticated
  USING (
    company_id IN (SELECT public.hr_company_ids())
    OR public.is_admin()
  )
  WITH CHECK (
    company_id IN (SELECT public.hr_company_ids())
    OR public.is_admin()
  );

-- Existing service_role all-true policy (company_preferred_suppliers_admin) is
-- left in place.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_preferred_suppliers TO authenticated;
REVOKE ALL ON public.company_preferred_suppliers FROM anon;

COMMIT;
