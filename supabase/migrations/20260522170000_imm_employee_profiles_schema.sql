-- =============================================================================
-- IMM-01 · Fix: employee_profiles full schema
--
-- The original IMM-01 migration (20260518120000) used CREATE TABLE IF NOT EXISTS
-- for employee_profiles, but the table already existed from the Feb 2026 schema
-- (20260221105601_remote_schema.sql) with a different design:
--   - assignment_id TEXT PK, profile_json JSONB, user_id UUID
--
-- That older table had 8 rows of data (pre-pilot test records).
--
-- This migration:
--   1. Renames the legacy table to legacy_employee_profiles (data preserved)
--   2. Creates the new employee_profiles with the full IMM-01 schema
--      (individual columns, pgcrypto, field_sources provenance, GDPR fields)
--   3. Re-applies indexes and RLS matching the IMM-01 design
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Rename legacy table (preserves all existing rows)
-- ---------------------------------------------------------------------------

ALTER TABLE public.employee_profiles
  RENAME TO legacy_employee_profiles;

COMMENT ON TABLE public.legacy_employee_profiles IS
  'Legacy employee profile blob (assignment_id + profile_json). '
  'Superseded by the new employee_profiles table (IMM-01). '
  'Preserved for data continuity — 8 pre-pilot test records.';

-- ---------------------------------------------------------------------------
-- 2. Create new employee_profiles — full immigration data vault
--    One record per case (not per employee — fresh consent each relocation).
-- ---------------------------------------------------------------------------

CREATE TABLE public.employee_profiles (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  case_id               TEXT NOT NULL,
  employee_id           TEXT NOT NULL,
  org_id                TEXT NOT NULL,

  -- Identity (Article 9 special category — explicit consent required)
  legal_first_name      TEXT,
  legal_last_name       TEXT,
  middle_names          TEXT,
  date_of_birth         DATE,
  place_of_birth        TEXT,
  nationality           TEXT,         -- ISO 3166-1 alpha-2 (e.g. 'FR')
  second_nationality    TEXT,
  gender                TEXT,

  -- Travel documents (passport_number encrypted at app layer via pgcrypto)
  passport_number       TEXT,         -- stored as pgp_sym_encrypt ciphertext
  passport_expiry       DATE,
  passport_issue_date   DATE,
  passport_country      TEXT,
  passport_mrz_line1    TEXT,
  passport_mrz_line2    TEXT,
  existing_visa_type    TEXT,
  existing_visa_expiry  DATE,
  prior_visa_refusals   BOOLEAN NOT NULL DEFAULT FALSE,

  -- Contact & address history
  current_address       JSONB,
  -- {street, city, postcode, country, from_date}
  address_history       JSONB NOT NULL DEFAULT '[]'::jsonb,
  -- [{street, city, postcode, country, from_date, to_date}]

  -- Employment (typically HR-provided)
  employer_name         TEXT,
  employer_reg_number   TEXT,
  employer_address      JSONB,
  job_title             TEXT,
  job_title_local       TEXT,         -- in destination language (e.g. German for DE)
  employment_start_date DATE,
  salary_amount         NUMERIC,
  salary_currency       TEXT NOT NULL DEFAULT 'EUR',
  contract_type         TEXT,         -- permanent | fixed-term | posted-worker

  -- Education (for Blue Card / skilled-worker visas)
  highest_qualification TEXT,
  institution           TEXT,
  graduation_year       INT,
  degree_anabin_status  TEXT,         -- recognised | not-recognised | pending (DE)

  -- Family
  marital_status        TEXT,
  spouse_name           TEXT,
  spouse_nationality    TEXT,
  spouse_dob            DATE,
  dependents            JSONB NOT NULL DEFAULT '[]'::jsonb,
  -- [{name, dob, nationality, relationship}]

  -- Data provenance — per-field source tracking (GDPR Article 5 — data accuracy)
  field_sources         JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- {field_name: "hr_provided" | "self_entered" | "ocr_extracted"}
  field_confidence      JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- {field_name: 0.0-1.0} for OCR-extracted fields
  field_conflicts       JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- {field_name: {source_a: val_a, source_b: val_b}} — needs human resolution

  -- GDPR
  consent_record_id     TEXT,         -- FK to consent_records.id
  consent_timestamp     TIMESTAMPTZ,
  consent_version       TEXT,
  consent_purposes      TEXT[],       -- ['immigration_processing', 'vendor_sharing']
  retention_expires_at  TIMESTAMPTZ,  -- case closure + 36 months; NULL until case closes

  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.employee_profiles IS
  'Immigration personal data vault. One record per relocation case '
  '(same employee relocating twice = two records with fresh consent). '
  'passport_number is stored as pgp_sym_encrypt ciphertext — '
  'never plain text. Governed by GDPR Article 9 (special category).';

COMMENT ON COLUMN public.employee_profiles.passport_number IS
  'Encrypted at application layer via pgp_sym_encrypt(value, ENCRYPTION_KEY). '
  'Decrypt with pgp_sym_decrypt(passport_number::bytea, ENCRYPTION_KEY). '
  'NEVER log or expose the plaintext value.';

COMMENT ON COLUMN public.employee_profiles.field_sources IS
  'Per-field provenance map: {"legal_first_name": "hr_provided", "passport_number": "ocr_extracted"}. '
  'Values: hr_provided | self_entered | ocr_extracted.';

COMMENT ON COLUMN public.employee_profiles.retention_expires_at IS
  'GDPR retention deadline. Set to NOW() + 36 months when case is closed. '
  'The nightly retention Edge Function deletes rows past this date.';

-- ---------------------------------------------------------------------------
-- 3. Indexes
-- ---------------------------------------------------------------------------

CREATE UNIQUE INDEX idx_employee_profiles_case_employee
  ON public.employee_profiles(case_id, employee_id);

CREATE INDEX idx_employee_profiles_case_id
  ON public.employee_profiles(case_id);

CREATE INDEX idx_employee_profiles_org_id
  ON public.employee_profiles(org_id);

CREATE INDEX idx_employee_profiles_retention
  ON public.employee_profiles(retention_expires_at)
  WHERE retention_expires_at IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. updated_at auto-update trigger
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.fn_employee_profiles_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_employee_profiles_updated_at
  BEFORE UPDATE ON public.employee_profiles
  FOR EACH ROW EXECUTE FUNCTION public.fn_employee_profiles_updated_at();

-- ---------------------------------------------------------------------------
-- 5. Row-Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE public.employee_profiles ENABLE ROW LEVEL SECURITY;

-- Employee reads their own profile(s)
DROP POLICY IF EXISTS employee_profiles_employee_select ON public.employee_profiles;
CREATE POLICY employee_profiles_employee_select
  ON public.employee_profiles FOR SELECT TO authenticated
  USING (employee_id = auth.uid()::text);

-- Employee updates their own profile (self-entered fields)
DROP POLICY IF EXISTS employee_profiles_employee_update ON public.employee_profiles;
CREATE POLICY employee_profiles_employee_update
  ON public.employee_profiles FOR UPDATE TO authenticated
  USING (employee_id = auth.uid()::text)
  WITH CHECK (employee_id = auth.uid()::text);

-- Employee creates their own profile (initial intake)
DROP POLICY IF EXISTS employee_profiles_employee_insert ON public.employee_profiles;
CREATE POLICY employee_profiles_employee_insert
  ON public.employee_profiles FOR INSERT TO authenticated
  WITH CHECK (employee_id = auth.uid()::text);

-- HR reads profiles for cases they are assigned to
DROP POLICY IF EXISTS employee_profiles_hr_select ON public.employee_profiles;
CREATE POLICY employee_profiles_hr_select
  ON public.employee_profiles FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = employee_profiles.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

-- HR updates profiles for cases they are assigned to (HR-provided fields)
DROP POLICY IF EXISTS employee_profiles_hr_update ON public.employee_profiles;
CREATE POLICY employee_profiles_hr_update
  ON public.employee_profiles FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = employee_profiles.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = employee_profiles.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

-- Service role (Edge Functions, backend jobs) full access
DROP POLICY IF EXISTS employee_profiles_service_role ON public.employee_profiles;
CREATE POLICY employee_profiles_service_role
  ON public.employee_profiles FOR ALL TO service_role
  USING (true) WITH CHECK (true);

COMMIT;
