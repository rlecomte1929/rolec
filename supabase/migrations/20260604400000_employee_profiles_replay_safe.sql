-- =============================================================================
-- IMM-01 · employee_profiles — replay-safe rebuild (drift entry 13)
-- =============================================================================
-- Canonical, idempotent rebuild of employee_profiles, replacing the two earlier
-- migrations that cannot run on a fresh `supabase db reset`:
--
--   * 20260518120000_immigration_core_tables.sql — its CREATE TABLE IF NOT EXISTS
--     silently no-ops against the Feb-2026 baseline table (assignment_id PK, no
--     case_id), then its case_id index aborts (SQLSTATE 42703). That block — and
--     its data_access_log_employee_select policy, which reads the new shape — are
--     now disabled there.
--   * 20260522170000_imm_employee_profiles_schema.sql — the original rename +
--     recreate; now a no-op (it and 20260518120000 both renamed the legacy table,
--     so they conflicted on a clean replay).
--
-- This migration reproduces the EXACT prod shape (51 columns, updated_at trigger,
-- COMMENTs, indexes, RLS + 6 policies) and is fully idempotent:
--   * fresh replay  → renames the Feb-2026 legacy table aside, builds the new shape.
--   * prod (already built) → every step is a guarded no-op; prod is NOT modified.
-- See audit/migration-drift-definitive-2026-06-02.md § reverse-drift entry 13.
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- 1. Move the Feb-2026 legacy blob table aside (only on a fresh replay).
--    Guard: skip entirely if legacy_employee_profiles already exists (prod) or
--    if employee_profiles is already the new shape (has case_id).
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF to_regclass('public.legacy_employee_profiles') IS NULL
     AND to_regclass('public.employee_profiles') IS NOT NULL
     AND NOT EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema = 'public'
         AND table_name = 'employee_profiles'
         AND column_name = 'case_id'
     )
  THEN
    ALTER TABLE public.employee_profiles RENAME TO legacy_employee_profiles;
    COMMENT ON TABLE public.legacy_employee_profiles IS
      'Legacy employee profile blob (assignment_id + profile_json). '
      'Superseded by the new employee_profiles table (IMM-01). '
      'Preserved for data continuity — pre-pilot test records.';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. New employee_profiles — full immigration data vault (prod shape).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.employee_profiles (
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_profiles_case_employee
  ON public.employee_profiles(case_id, employee_id);

CREATE INDEX IF NOT EXISTS idx_employee_profiles_case_id
  ON public.employee_profiles(case_id);

CREATE INDEX IF NOT EXISTS idx_employee_profiles_org_id
  ON public.employee_profiles(org_id);

CREATE INDEX IF NOT EXISTS idx_employee_profiles_retention
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

DROP TRIGGER IF EXISTS trg_employee_profiles_updated_at ON public.employee_profiles;
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

-- ---------------------------------------------------------------------------
-- 6. Rebuild the data_access_log_employee_select policy that
--    20260518120000 had to disable (it reads employee_profiles(id, employee_id),
--    which only exists once the table above is created on a fresh replay).
--    Guarded so it runs only if data_access_log is present.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF to_regclass('public.data_access_log') IS NOT NULL THEN
    DROP POLICY IF EXISTS data_access_log_employee_select ON public.data_access_log;
    CREATE POLICY data_access_log_employee_select
      ON public.data_access_log FOR SELECT TO authenticated
      USING (
        EXISTS (
          SELECT 1 FROM public.employee_profiles ep
          WHERE ep.id = data_access_log.profile_id
            AND ep.employee_id = auth.uid()::text
        )
      );
  END IF;
END $$;

COMMIT;
