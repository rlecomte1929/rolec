-- =============================================================================
-- IMM-01 · Immigration Intelligence System — Core Tables
--
-- Creates 6 new tables for the full immigration guidance feature:
--
--   1. employee_profiles       — personal data vault (encrypted passport_number)
--   2. immigration_requirements — corridor × visa_type → document matrix
--   3. interview_sessions      — DAG interview state machine persistence
--   4. immigration_milestones  — application lifecycle tracker
--   5. consent_records         — immutable GDPR consent ledger (append-only)
--   6. data_access_log         — immutable audit trail (append-only)
--
-- GDPR notes:
--   - passport_number is encrypted via pgcrypto (pgp_sym_encrypt / pgp_sym_decrypt)
--     using an app-level ENCRYPTION_KEY env var — never stored in plain text.
--   - consent_records and data_access_log are append-only:
--     UPDATE and DELETE are blocked via BEFORE triggers that RAISE EXCEPTION.
--   - RLS is enabled on all tables.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- 1. employee_profiles
--    One record per case (not per employee — fresh consent required each time).
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

  -- Travel documents (passport_number encrypted at app layer)
  passport_number       TEXT,         -- stored as pgp_sym_encrypt ciphertext
  passport_expiry       DATE,
  passport_issue_date   DATE,
  passport_country      TEXT,
  passport_mrz_line1    TEXT,
  passport_mrz_line2    TEXT,
  existing_visa_type    TEXT,
  existing_visa_expiry  DATE,
  prior_visa_refusals   BOOLEAN DEFAULT FALSE,

  -- Contact & address history
  current_address       JSONB,
  -- [{street, city, postcode, country, from_date, to_date}]
  address_history       JSONB DEFAULT '[]'::jsonb,

  -- Employment (typically HR-provided, locked from employee edit)
  employer_name         TEXT,
  employer_reg_number   TEXT,
  employer_address      JSONB,
  job_title             TEXT,
  job_title_local       TEXT,         -- in destination language
  employment_start_date DATE,
  salary_amount         NUMERIC,
  salary_currency       TEXT DEFAULT 'EUR',
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
  dependents            JSONB DEFAULT '[]'::jsonb,
  -- [{name, dob, nationality, relationship}]

  -- Data provenance — per-field source tracking
  field_sources         JSONB DEFAULT '{}'::jsonb,
  -- {field_name: "hr_provided" | "self_entered" | "ocr_extracted"}
  field_confidence      JSONB DEFAULT '{}'::jsonb,
  -- {field_name: 0.0-1.0} for OCR fields
  field_conflicts       JSONB DEFAULT '{}'::jsonb,
  -- {field_name: {source_a: val_a, source_b: val_b}} — needs human resolution

  -- GDPR
  consent_record_id     TEXT,         -- FK to consent_records.id
  consent_timestamp     TIMESTAMPTZ,
  consent_version       TEXT,
  consent_purposes      TEXT[],       -- ['immigration_processing', 'vendor_sharing']
  retention_expires_at  TIMESTAMPTZ,  -- set at case closure + 36 months

  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_profiles_case_employee
  ON public.employee_profiles(case_id, employee_id);

CREATE INDEX IF NOT EXISTS idx_employee_profiles_case_id
  ON public.employee_profiles(case_id);

CREATE INDEX IF NOT EXISTS idx_employee_profiles_org_id
  ON public.employee_profiles(org_id);

CREATE INDEX IF NOT EXISTS idx_employee_profiles_retention
  ON public.employee_profiles(retention_expires_at)
  WHERE retention_expires_at IS NOT NULL;

ALTER TABLE public.employee_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS employee_profiles_employee_select ON public.employee_profiles;
CREATE POLICY employee_profiles_employee_select
  ON public.employee_profiles FOR SELECT TO authenticated
  USING (employee_id = auth.uid()::text);

DROP POLICY IF EXISTS employee_profiles_employee_update ON public.employee_profiles;
CREATE POLICY employee_profiles_employee_update
  ON public.employee_profiles FOR UPDATE TO authenticated
  USING (employee_id = auth.uid()::text)
  WITH CHECK (employee_id = auth.uid()::text);

DROP POLICY IF EXISTS employee_profiles_employee_insert ON public.employee_profiles;
CREATE POLICY employee_profiles_employee_insert
  ON public.employee_profiles FOR INSERT TO authenticated
  WITH CHECK (employee_id = auth.uid()::text);

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

DROP POLICY IF EXISTS employee_profiles_hr_update ON public.employee_profiles;
CREATE POLICY employee_profiles_hr_update
  ON public.employee_profiles FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = employee_profiles.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS employee_profiles_service_role ON public.employee_profiles;
CREATE POLICY employee_profiles_service_role
  ON public.employee_profiles FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- 2. immigration_requirements
--    Corridor × visa_type → required document definitions.
--    Seeded by IMM-03. Updated by ReloPass team.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.immigration_requirements (
  id                        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,

  -- Key dimensions
  corridor_from             TEXT NOT NULL,   -- ISO country code, e.g. 'FR'
  corridor_to               TEXT NOT NULL,   -- ISO country code, e.g. 'DE'
  visa_type                 TEXT NOT NULL,
  -- blue_card | skilled_worker | ict | posted_worker | long_stay_work |
  -- skilled_worker_uk | l1 | o1 | employment_pass
  employee_type             TEXT NOT NULL DEFAULT 'any',
  -- any | eu_citizen | non_eu

  -- Document identity
  document_type             TEXT NOT NULL,   -- canonical slug, e.g. 'passport'
  document_name             TEXT NOT NULL,   -- human-readable

  -- Requirement flags
  is_required               BOOLEAN NOT NULL DEFAULT TRUE,
  is_conditional            BOOLEAN NOT NULL DEFAULT FALSE,
  condition_expression      TEXT,
  -- e.g. "has_dependents = true" — evaluated by requirement service

  -- Processing metadata
  freshness_days            INT,             -- max age at submission (NULL = no limit)
  requires_apostille        BOOLEAN NOT NULL DEFAULT FALSE,
  apostille_countries       TEXT[],
  requires_translation      BOOLEAN NOT NULL DEFAULT FALSE,
  translation_languages     TEXT[],

  -- Pre-fill / OCR capabilities
  can_be_prefilled          BOOLEAN NOT NULL DEFAULT FALSE,
  can_be_ocr_extracted      BOOLEAN NOT NULL DEFAULT FALSE,
  vault_field_mapping       TEXT,

  -- Timeline
  typical_processing_days   INT,
  book_early_flag           BOOLEAN NOT NULL DEFAULT FALSE,
  book_early_reason         TEXT,

  -- Guidance content
  success_tips              TEXT[],
  common_rejection_reasons  TEXT[],

  -- Form references
  form_url                  TEXT,
  form_version              TEXT,
  instructions_url          TEXT,

  -- Data quality
  last_verified_date        DATE,
  source                    TEXT DEFAULT 'relopass_team',
  -- fragomen | official_gov | relopass_team

  created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_immigration_requirements_key
  ON public.immigration_requirements(corridor_from, corridor_to, visa_type, employee_type, document_type);

CREATE INDEX IF NOT EXISTS idx_immigration_requirements_corridor
  ON public.immigration_requirements(corridor_from, corridor_to, visa_type);

ALTER TABLE public.immigration_requirements ENABLE ROW LEVEL SECURITY;

-- Public read (all authenticated users can look up requirements)
DROP POLICY IF EXISTS immigration_requirements_select ON public.immigration_requirements;
CREATE POLICY immigration_requirements_select
  ON public.immigration_requirements FOR SELECT TO authenticated
  USING (true);

DROP POLICY IF EXISTS immigration_requirements_service_role ON public.immigration_requirements;
CREATE POLICY immigration_requirements_service_role
  ON public.immigration_requirements FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- 3. interview_sessions
--    Tracks DAG traversal state for the smart interview engine.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.interview_sessions (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  case_id               TEXT NOT NULL,
  employee_id           TEXT NOT NULL,
  org_id                TEXT NOT NULL,

  -- DAG state
  current_section       TEXT,
  -- identity | travel_docs | address_history | employment | family
  current_question_id   TEXT,
  answers               JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- {question_id: answer_value}
  skipped_fields        TEXT[],       -- fields skipped (vault already had data)
  prefilled_fields      TEXT[],       -- fields shown with existing vault data
  pending_confirmations TEXT[],       -- pre-filled fields not yet confirmed by employee

  -- Progress
  completed_sections    TEXT[] NOT NULL DEFAULT '{}',
  completion_pct        INT NOT NULL DEFAULT 0,

  -- GDPR
  consent_record_id     TEXT,

  started_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_active_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at          TIMESTAMPTZ,

  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_interview_sessions_case_employee
  ON public.interview_sessions(case_id, employee_id);

CREATE INDEX IF NOT EXISTS idx_interview_sessions_case_id
  ON public.interview_sessions(case_id);

ALTER TABLE public.interview_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS interview_sessions_employee ON public.interview_sessions;
CREATE POLICY interview_sessions_employee
  ON public.interview_sessions FOR ALL TO authenticated
  USING (employee_id = auth.uid()::text)
  WITH CHECK (employee_id = auth.uid()::text);

DROP POLICY IF EXISTS interview_sessions_hr_select ON public.interview_sessions;
CREATE POLICY interview_sessions_hr_select
  ON public.interview_sessions FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = interview_sessions.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS interview_sessions_service_role ON public.interview_sessions;
CREATE POLICY interview_sessions_service_role
  ON public.interview_sessions FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- 4. immigration_milestones
--    Application lifecycle tracker — preflight → visa issued → permit renewal.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.immigration_milestones (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  case_id               TEXT NOT NULL,
  org_id                TEXT NOT NULL,

  milestone_type        TEXT NOT NULL,
  -- preflight_check | dossier_assembly | criminal_record_ordered |
  -- application_filed | biometric_appointment | visa_decision |
  -- visa_issued | arrival | local_registration | work_permit_issued |
  -- permit_renewal_reminder

  status                TEXT NOT NULL DEFAULT 'pending',
  -- pending | in_progress | completed | blocked | not_applicable

  sort_order            INT NOT NULL DEFAULT 0,
  target_date           DATE,
  completed_date        DATE,
  notes                 TEXT,
  evidence_url          TEXT,         -- uploaded proof (e.g. visa scan)
  book_early_alert      TEXT,         -- shown prominently if set

  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_immigration_milestones_case_id
  ON public.immigration_milestones(case_id);

CREATE INDEX IF NOT EXISTS idx_immigration_milestones_status
  ON public.immigration_milestones(case_id, status);

ALTER TABLE public.immigration_milestones ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS immigration_milestones_select ON public.immigration_milestones;
CREATE POLICY immigration_milestones_select
  ON public.immigration_milestones FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = immigration_milestones.case_id
        AND (ca.employee_user_id = auth.uid()::text OR ca.hr_user_id = auth.uid()::text)
    )
  );

DROP POLICY IF EXISTS immigration_milestones_hr_write ON public.immigration_milestones;
CREATE POLICY immigration_milestones_hr_write
  ON public.immigration_milestones FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = immigration_milestones.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = immigration_milestones.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS immigration_milestones_service_role ON public.immigration_milestones;
CREATE POLICY immigration_milestones_service_role
  ON public.immigration_milestones FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- 5. consent_records
--    Immutable GDPR consent ledger. Append-only — never delete or update rows.
--    A consent withdrawal is a NEW row with consented=false, not an update.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.consent_records (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  employee_id           TEXT NOT NULL,
  case_id               TEXT NOT NULL,

  purpose               TEXT NOT NULL,
  -- immigration_processing | vendor_sharing | analytics
  consented             BOOLEAN NOT NULL,
  consent_version       TEXT NOT NULL,   -- version of consent text shown
  consent_text_hash     TEXT NOT NULL,   -- SHA-256 of exact text shown (proof)

  consented_at          TIMESTAMPTZ,
  withdrawn_at          TIMESTAMPTZ,     -- set on a NEW withdrawal row
  withdrawn_reason      TEXT,

  ip_address            TEXT,
  user_agent            TEXT,

  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
  -- NO updated_at — this table is append-only
);

CREATE INDEX IF NOT EXISTS idx_consent_records_case_employee
  ON public.consent_records(case_id, employee_id);

CREATE INDEX IF NOT EXISTS idx_consent_records_employee_purpose
  ON public.consent_records(employee_id, purpose);

ALTER TABLE public.consent_records ENABLE ROW LEVEL SECURITY;

-- Employees can read their own consent records
DROP POLICY IF EXISTS consent_records_employee_select ON public.consent_records;
CREATE POLICY consent_records_employee_select
  ON public.consent_records FOR SELECT TO authenticated
  USING (employee_id = auth.uid()::text);

-- Employees can insert (give consent)
DROP POLICY IF EXISTS consent_records_employee_insert ON public.consent_records;
CREATE POLICY consent_records_employee_insert
  ON public.consent_records FOR INSERT TO authenticated
  WITH CHECK (employee_id = auth.uid()::text);

-- HR can read consent for their cases
DROP POLICY IF EXISTS consent_records_hr_select ON public.consent_records;
CREATE POLICY consent_records_hr_select
  ON public.consent_records FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = consent_records.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

-- Service role can also insert (backend-side consent recording)
DROP POLICY IF EXISTS consent_records_service_role ON public.consent_records;
CREATE POLICY consent_records_service_role
  ON public.consent_records FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- APPEND-ONLY ENFORCEMENT: block UPDATE and DELETE for ALL roles
-- Including service_role — enforced at trigger level, not just RLS.
CREATE OR REPLACE FUNCTION public.fn_consent_records_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION
    'consent_records is append-only. Withdrawals must be inserted as new rows '
    '(consented=false), not updates or deletes. '
    'Operation % on row % is not permitted.',
    TG_OP, OLD.id;
END;
$$;

DROP TRIGGER IF EXISTS trg_consent_records_immutable ON public.consent_records;
CREATE TRIGGER trg_consent_records_immutable
  BEFORE UPDATE OR DELETE ON public.consent_records
  FOR EACH ROW EXECUTE FUNCTION public.fn_consent_records_immutable();

-- ---------------------------------------------------------------------------
-- 6. data_access_log
--    Immutable audit trail for all accesses to immigration personal data.
--    Append-only — enforced by trigger.
--    Used for GDPR Article 30 Records of Processing Activities.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.data_access_log (
  id                    BIGSERIAL PRIMARY KEY,
  case_id               TEXT,
  profile_id            TEXT,         -- FK to employee_profiles.id
  accessed_by_user_id   TEXT NOT NULL,
  accessed_by_role      TEXT NOT NULL,
  -- hr | admin | employee | vendor | system

  action                TEXT NOT NULL,
  -- view | edit | export | delete | vendor_share | ocr_extract | consent_record

  fields_accessed       TEXT[],       -- list of field names accessed/changed
  -- NOTE: never log the actual VALUES of sensitive fields

  purpose               TEXT,
  vendor_name           TEXT,         -- if action = 'vendor_share'
  vendor_dpa_ref        TEXT,         -- reference to signed DPA on file

  accessed_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ip_address            TEXT
  -- NO updated_at — append-only
);

CREATE INDEX IF NOT EXISTS idx_data_access_log_case_id
  ON public.data_access_log(case_id);

CREATE INDEX IF NOT EXISTS idx_data_access_log_profile_id
  ON public.data_access_log(profile_id);

CREATE INDEX IF NOT EXISTS idx_data_access_log_user_id
  ON public.data_access_log(accessed_by_user_id);

CREATE INDEX IF NOT EXISTS idx_data_access_log_accessed_at
  ON public.data_access_log(accessed_at);

ALTER TABLE public.data_access_log ENABLE ROW LEVEL SECURITY;

-- Anyone authenticated can INSERT (backend logs on behalf of users)
DROP POLICY IF EXISTS data_access_log_insert ON public.data_access_log;
CREATE POLICY data_access_log_insert
  ON public.data_access_log FOR INSERT TO authenticated
  WITH CHECK (true);

-- Employees can read their own access log (for the data export endpoint)
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

-- HR can read access log for their cases
DROP POLICY IF EXISTS data_access_log_hr_select ON public.data_access_log;
CREATE POLICY data_access_log_hr_select
  ON public.data_access_log FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = data_access_log.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

DROP POLICY IF EXISTS data_access_log_service_role ON public.data_access_log;
CREATE POLICY data_access_log_service_role
  ON public.data_access_log FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- APPEND-ONLY ENFORCEMENT: block UPDATE and DELETE for ALL roles
CREATE OR REPLACE FUNCTION public.fn_data_access_log_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION
    'data_access_log is append-only. '
    'Operation % on row % is not permitted. '
    'This table is the GDPR audit trail and must not be modified.',
    TG_OP, OLD.id;
END;
$$;

DROP TRIGGER IF EXISTS trg_data_access_log_immutable ON public.data_access_log;
CREATE TRIGGER trg_data_access_log_immutable
  BEFORE UPDATE OR DELETE ON public.data_access_log
  FOR EACH ROW EXECUTE FUNCTION public.fn_data_access_log_immutable();

-- ---------------------------------------------------------------------------
-- GDPR Audit Summary View
-- Used by DPO / compliance dashboard.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW public.vw_gdpr_audit_summary AS
SELECT
  dal.case_id,
  dal.profile_id,
  dal.accessed_by_role,
  dal.action,
  DATE_TRUNC('week', dal.accessed_at) AS week_start,
  COUNT(*)                             AS access_count,
  ARRAY_AGG(DISTINCT dal.purpose)      AS purposes,
  ARRAY_AGG(DISTINCT dal.vendor_name) FILTER (WHERE dal.vendor_name IS NOT NULL) AS vendors
FROM public.data_access_log dal
GROUP BY
  dal.case_id, dal.profile_id, dal.accessed_by_role, dal.action,
  DATE_TRUNC('week', dal.accessed_at);

COMMENT ON VIEW public.vw_gdpr_audit_summary IS
  'Weekly aggregation of immigration data accesses for GDPR Article 30 compliance. '
  'Use this view when a DPO needs to demonstrate records of processing activities. '
  'Raw log (field-level) is in data_access_log.';

-- ---------------------------------------------------------------------------
-- form_field_mappings
--    Maps vault fields to specific government form fields (for PDF pre-fill).
--    Seeded by IMM-11.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.form_field_mappings (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  form_id               TEXT NOT NULL,   -- e.g. 'DE_blue_card_v2024'
  form_name             TEXT NOT NULL,
  corridor_to           TEXT NOT NULL,
  visa_type             TEXT NOT NULL,
  form_url              TEXT,

  form_field_id         TEXT NOT NULL,   -- AcroForm field name
  form_field_label      TEXT,            -- human label in the form

  vault_field_path      TEXT NOT NULL,   -- field name in employee_profiles
  format_rule           TEXT,
  -- uppercase | passport_format | dd/mm/yyyy | yyyy-mm-dd | name_normalise
  exact_match_required  BOOLEAN NOT NULL DEFAULT FALSE,
  max_length            INT,
  validation_regex      TEXT,
  field_instruction     TEXT,
  example_value         TEXT,

  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_form_field_mappings_form
  ON public.form_field_mappings(form_id);

CREATE INDEX IF NOT EXISTS idx_form_field_mappings_corridor
  ON public.form_field_mappings(corridor_to, visa_type);

ALTER TABLE public.form_field_mappings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS form_field_mappings_select ON public.form_field_mappings;
CREATE POLICY form_field_mappings_select
  ON public.form_field_mappings FOR SELECT TO authenticated
  USING (true);

DROP POLICY IF EXISTS form_field_mappings_service_role ON public.form_field_mappings;
CREATE POLICY form_field_mappings_service_role
  ON public.form_field_mappings FOR ALL TO service_role
  USING (true) WITH CHECK (true);

COMMIT;
