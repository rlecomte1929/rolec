-- AIQ-1602 Seg 4: HR "register a preferred supplier" → admin moderation queue.
--
-- HR submits a minimal supplier proposal (name + category + coverage + contact).
-- It lands here as `pending`; a platform admin approves it into the shared
-- public.suppliers registry (via supplier_registry.create_supplier) or rejects
-- it. HR NEVER writes the shared registry directly — this table is the trust
-- boundary. Per-company scoped for HR reads/writes; admins see all.
--
-- Mirrors the RLS pattern in 20260824000000_company_preferred_suppliers_hr_rls.sql
-- (canonical public.hr_company_ids() + public.is_admin()). Idempotent.

BEGIN;

CREATE TABLE IF NOT EXISTS public.hr_supplier_submissions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id          uuid NOT NULL,
  submitted_by_user_id uuid,
  name                text NOT NULL,
  service_category    text NOT NULL,
  coverage_scope_type text NOT NULL DEFAULT 'country',
  country_code        text,
  city_name           text,
  contact_email       text,
  status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected')),
  reviewed_by         uuid,
  reviewed_at         timestamptz,
  review_notes        text,
  created_supplier_id text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS hr_supplier_submissions_status_idx
  ON public.hr_supplier_submissions (status, created_at DESC);
CREATE INDEX IF NOT EXISTS hr_supplier_submissions_company_idx
  ON public.hr_supplier_submissions (company_id, created_at DESC);

-- SEC-002 hard gate: RLS + policy + REVOKE anon on every new public table.
ALTER TABLE public.hr_supplier_submissions ENABLE ROW LEVEL SECURITY;

-- HR: read/write only their own company's submissions; admins carved out.
DROP POLICY IF EXISTS hr_supplier_submissions_company_scoped
  ON public.hr_supplier_submissions;
CREATE POLICY hr_supplier_submissions_company_scoped
  ON public.hr_supplier_submissions
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

-- Service-role (backend) bypass, matching the established pattern.
DROP POLICY IF EXISTS hr_supplier_submissions_service_role
  ON public.hr_supplier_submissions;
CREATE POLICY hr_supplier_submissions_service_role
  ON public.hr_supplier_submissions
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.hr_supplier_submissions TO authenticated;
REVOKE ALL ON public.hr_supplier_submissions FROM anon;

COMMIT;
