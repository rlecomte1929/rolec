-- Land the tenant RLS policies for public.services_state against its REAL schema.
--
-- Background. 20260427110000_services_state.sql was written for a uuid-keyed table
-- (case_id / organization_id / updated_by_user_id all uuid). The table that actually
-- exists in production is text-keyed on all three columns -- it was created
-- out-of-band, never by that migration, and no ORM model defines it. So the original
-- migration's `create table if not exists` no-ops, and its policies then fail with
--   ERROR: operator does not exist: text = uuid (SQLSTATE 42883)
-- because they compare a text organization_id against profiles.company_id (uuid).
--
-- Result measured on prod 2026-08-19: services_state has RLS enabled, 334 live rows,
-- and exactly ONE policy (services_state_service_role). Both tenant policies from the
-- April migration are missing. That is currently safe -- RLS on with no policy for
-- anon/authenticated is deny-by-default, and the backend reads via the service role --
-- but the intended tenant scoping never landed. This lands it.
--
-- Why a new file rather than editing 20260427110000: migrations are append-only, and
-- that file is not in the production ledger (it is the head of the pending queue). It
-- also creates trg_audit_services_state, which 20260731000000 -- already applied --
-- deliberately dropped (it wrote a duplicate audit_logs row per save carrying the whole
-- state_json blob, up to 256 KB, attributed to 'system' instead of the real user).
-- This migration must NOT resurrect that trigger, and does not.
--
-- Types on prod, verified 2026-08-19:
--   services_state.organization_id  text
--   profiles.id                     uuid
--   profiles.company_id             uuid
-- Hence the cast goes on profiles.company_id (uuid -> text), not on organization_id.
--
-- Idempotent: DROP POLICY IF EXISTS before each CREATE POLICY. No schema change, no
-- data change, no trigger change.

BEGIN;

-- Guard: refuse to run if the table is not the text-keyed shape this file targets.
-- If someone later migrates services_state to uuid keys, this fails loudly rather
-- than silently installing a policy that never matches a row.
DO $$
BEGIN
  IF (SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'services_state'
          AND column_name  = 'organization_id') IS DISTINCT FROM 'text'
  THEN
    RAISE EXCEPTION
      'services_state.organization_id is not text -- this migration targets the '
      'text-keyed production shape. Re-derive the cast before applying.';
  END IF;
END $$;

DROP POLICY IF EXISTS services_state_select_tenant ON public.services_state;
CREATE POLICY services_state_select_tenant
  ON public.services_state
  FOR SELECT
  TO authenticated
  USING (
    organization_id IN (
      SELECT company_id::text FROM public.profiles
       WHERE id = auth.uid() AND company_id IS NOT NULL
    )
  );

DROP POLICY IF EXISTS services_state_insert_tenant ON public.services_state;
CREATE POLICY services_state_insert_tenant
  ON public.services_state
  FOR INSERT
  TO authenticated
  WITH CHECK (
    organization_id IN (
      SELECT company_id::text FROM public.profiles
       WHERE id = auth.uid() AND company_id IS NOT NULL
    )
  );

DROP POLICY IF EXISTS services_state_update_tenant ON public.services_state;
CREATE POLICY services_state_update_tenant
  ON public.services_state
  FOR UPDATE
  TO authenticated
  USING (
    organization_id IN (
      SELECT company_id::text FROM public.profiles
       WHERE id = auth.uid() AND company_id IS NOT NULL
    )
  )
  WITH CHECK (
    organization_id IN (
      SELECT company_id::text FROM public.profiles
       WHERE id = auth.uid() AND company_id IS NOT NULL
    )
  );

-- Defense-in-depth: the anon key ships in the frontend bundle.
REVOKE ALL ON public.services_state FROM anon;

COMMIT;
