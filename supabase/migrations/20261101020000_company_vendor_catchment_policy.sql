-- [Stage 9 · Phase 1] Per-company switch for neighbour inclusion.
--
-- Neighbours are DEFAULT-INCLUDED for origin-sourced categories (product decision,
-- 2026-08-13), so a Strasbourg employee sees Kehl movers without anyone configuring anything.
-- This table is how a company turns that off — a tier-2, applies-to-all-routes preference.
--
-- Distinct from `company_vendor_catchment` (Addendum A §A.5), which is tier 3: the specific
-- extra countries HR adds for one corridor, each with a reason and an actor. That table lands
-- in Phase 3 with the rest of the curation schema. The two audit documents name them
-- differently; they are two different things, not a conflict.
--
-- Absence of a row means neighbours are included. A company that never touches this behaves
-- exactly as the default describes, so no backfill is needed.
BEGIN;

CREATE TABLE IF NOT EXISTS public.company_vendor_catchment_policy (
  company_id         text        PRIMARY KEY,
  include_neighbours boolean     NOT NULL DEFAULT true,
  updated_by_user_id uuid,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_vendor_catchment_policy IS
  'Tier-2 catchment preference: whether default-included neighbouring countries widen this '
  'company''s origin-sourced vendor catchment. No row = included (the default).';

ALTER TABLE public.company_vendor_catchment_policy ENABLE ROW LEVEL SECURITY;

-- HR sees and edits only their own company; admins carved out. Mirrors
-- hr_supplier_submissions_company_scoped (20260928000000).
DROP POLICY IF EXISTS company_vendor_catchment_policy_company_scoped
  ON public.company_vendor_catchment_policy;
CREATE POLICY company_vendor_catchment_policy_company_scoped
  ON public.company_vendor_catchment_policy
  FOR ALL
  TO authenticated
  USING (
    company_id::text IN (SELECT public.hr_company_ids())
    OR public.is_admin()
  )
  WITH CHECK (
    company_id::text IN (SELECT public.hr_company_ids())
    OR public.is_admin()
  );

DROP POLICY IF EXISTS company_vendor_catchment_policy_service_role
  ON public.company_vendor_catchment_policy;
CREATE POLICY company_vendor_catchment_policy_service_role
  ON public.company_vendor_catchment_policy
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_vendor_catchment_policy TO authenticated;
REVOKE ALL ON public.company_vendor_catchment_policy FROM anon;

COMMIT;
