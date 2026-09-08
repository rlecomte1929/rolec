-- Migration: 20260522200000_add_pets.sql
-- Purpose:   Create the public.pets table backing the Pets section
--            (replaces the embedded pets[] array previously stored in
--             cases.draft_json by /api/cases/{case_id}/household).
-- Task:      AIQ-288 (AIQ-160-A)  Created: 2026-05-22

-- ─── Table ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.pets (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id              uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  name                 text,
  species              text NOT NULL,
  breed                text,
  microchip_number     text,
  date_of_birth        date,
  passport_number      text,
  health_cert_expiry   date,
  vaccinations         jsonb NOT NULL DEFAULT '[]'::jsonb,
  vet_name             text,
  vet_phone            text,
  vet_country          char(2),
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT pets_vaccinations_is_array
    CHECK (jsonb_typeof(vaccinations) = 'array')
);

COMMENT ON TABLE public.pets IS
  'Per-case pets travelling with the employee. Multiple pets per case is the expected state — no UNIQUE constraint on case_id.';

-- ─── Indexes ─────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_pets_case_id
  ON public.pets (case_id);

-- ─── updated_at trigger ───────────────────────────────────────────────────────

CREATE OR REPLACE TRIGGER trg_pets_updated_at
  BEFORE UPDATE ON public.pets
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─── RLS ─────────────────────────────────────────────────────────────────────

ALTER TABLE public.pets ENABLE ROW LEVEL SECURITY;

-- Case-scoped read+write: employee owns the case, OR HR/admin in the same company.
-- Pattern matches case_forms / dossier_packages from 20260521000000_dossier_forms_core.sql.
DROP POLICY IF EXISTS pets_via_case ON public.pets;
CREATE POLICY pets_via_case ON public.pets FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ))
  WITH CHECK (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ));
