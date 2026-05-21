-- ============================================================
-- [P1-1] DOSSIER & FORMS — CORE SCHEMA
-- Date: 2026-05-21  |  Phase 1 foundation for the Dossier & Forms feature
--
-- Creates the normalized 3-table form model that supports per-field
-- AI confidence tracking, override loops (P4-6), and dossier export (P3+).
--
-- Tables:
--   1. form_templates           — catalog of available government forms
--   2. case_forms               — per-case instance of a form template
--   3. case_form_field_values   — per-field value with provenance
--   4. dossier_packages         — bundle export (ordered set of case_forms)
--
-- Plus: document_status enum (8 lifecycle states).
--
-- Adaptation notes (vs. original P1-1 spec):
--   - spec "assignment_id → assignments" → case_id → public.cases (no assignments table)
--   - spec "authority_id → authorities"  → authority_code text + authority_name text
--                                          (no authorities table; matches public.forms convention)
--   - spec "person_id → persons"         → person_id uuid → public.profiles (nullable)
--   - spec "created_by → users"          → created_by uuid → public.profiles
--   - All IDs are uuid (matches platform_redesign_schema target convention).
--
-- Coexistence with public.forms:
--   public.forms (created 2026-05-20 in platform_redesign_schema) is the
--   denormalized v1 model. case_forms is the v2 normalized model required
--   by Phase 2+ tasks (per-field AI provenance, override loop, dossier export).
--   These coexist for now; public.forms can be deprecated once the new
--   model is wired up end-to-end. Do not write new code against public.forms.
-- ============================================================

-- ============================================================
-- ENUM: document_status
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
    CREATE TYPE public.document_status AS ENUM (
      'not_started',
      'auto_filled',
      'in_progress',
      'pending_doc',
      'ready',
      'submitted',
      'approved',
      'rejected'
    );
  END IF;
END$$;

-- ============================================================
-- TABLE: form_templates
-- Catalog of available government forms (e.g. UTL-2011, RF-1234).
-- One row per form_code+version. Seeded by ReloPass ops team.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.form_templates (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code               text NOT NULL,                 -- e.g. 'UTL-2011'
  name               text NOT NULL,                 -- e.g. 'Declaration of Arrival'
  authority_code     text,                          -- e.g. 'UDI', 'OFII'
  authority_name     text,                          -- e.g. 'Norwegian Directorate of Immigration'
  country            char(2) NOT NULL,              -- ISO 3166-1 alpha-2, e.g. 'NO'
  category           text,                          -- e.g. 'registration', 'work_permit'
  original_pdf_url   text,
  fields             jsonb NOT NULL DEFAULT '[]',   -- array of FieldDefinition objects (see P1-2)
  trigger_rules      jsonb NOT NULL DEFAULT '{}',   -- when this template should be applied to a case
  version            text NOT NULL DEFAULT '1.0.0',
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT form_templates_code_version_unique UNIQUE (code, version)
);

COMMENT ON TABLE public.form_templates IS 'Catalog of government forms. Each row defines the schema, field layout, and trigger rules for one form (code, version). Instantiated per case via case_forms.';
COMMENT ON COLUMN public.form_templates.fields IS 'Array of FieldDefinition objects describing each form field: {id, label, type, position, required, ...}. Shape defined in P1-2 Form Template Registry.';
COMMENT ON COLUMN public.form_templates.trigger_rules IS 'JSONB rule that decides when this template applies to a case (e.g. {dest_country: "NO", pathway: "eea_registration"}). Consumed by the Trigger Engine (P1-3).';

CREATE INDEX IF NOT EXISTS idx_form_templates_code            ON public.form_templates(code);
CREATE INDEX IF NOT EXISTS idx_form_templates_country         ON public.form_templates(country);
CREATE INDEX IF NOT EXISTS idx_form_templates_category        ON public.form_templates(category);

-- ============================================================
-- TABLE: case_forms
-- Per-case instance of a form_template. The unit of work shown
-- in the Dossier list view (P1-5).
-- ============================================================
CREATE TABLE IF NOT EXISTS public.case_forms (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id            uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  form_template_id   uuid NOT NULL REFERENCES public.form_templates(id) ON DELETE RESTRICT,
  person_id          uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  status             public.document_status NOT NULL DEFAULT 'not_started',
  completion_pct     int  NOT NULL DEFAULT 0 CHECK (completion_pct BETWEEN 0 AND 100),
  deadline           date,
  deadline_trigger   text,                          -- e.g. 'within_7_days_of_arrival'
  blocker_form_id    uuid REFERENCES public.case_forms(id) ON DELETE SET NULL,
  original_file_url  text,
  draft_pdf_url      text,
  submitted_at       timestamptz,
  receipt_ref        text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.case_forms IS 'Per-case instance of a form_template. Status drives the badge in the Dossier list view (P1-5). Completion % computed from case_form_field_values.';
COMMENT ON COLUMN public.case_forms.blocker_form_id IS 'If this form cannot proceed until another form is submitted (e.g. work permit blocks tax registration), point to the blocking case_form.';
COMMENT ON COLUMN public.case_forms.deadline_trigger IS 'Symbolic deadline rule (e.g. "within_7_days_of_arrival"). Resolved to an absolute date by the deadline cron (P4-4).';

CREATE INDEX IF NOT EXISTS idx_case_forms_case_id              ON public.case_forms(case_id);
CREATE INDEX IF NOT EXISTS idx_case_forms_status               ON public.case_forms(status);
CREATE INDEX IF NOT EXISTS idx_case_forms_person_id            ON public.case_forms(person_id);
CREATE INDEX IF NOT EXISTS idx_case_forms_form_template_id     ON public.case_forms(form_template_id);

-- ============================================================
-- TABLE: case_form_field_values
-- Per-field value with provenance (filled_by, ai_confidence,
-- reviewed, overridden). The audit substrate for the AI
-- confidence improvement loop (P4-6).
-- ============================================================
CREATE TABLE IF NOT EXISTS public.case_form_field_values (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_form_id       uuid NOT NULL REFERENCES public.case_forms(id) ON DELETE CASCADE,
  field_id           text NOT NULL,                 -- matches form_templates.fields[].id
  value              text,
  filled_by          text NOT NULL
                       CHECK (filled_by IN ('ai', 'system', 'employee', 'specialist', 'hr')),
  ai_confidence      real,                          -- nullable; only set when filled_by='ai'
  reviewed           boolean NOT NULL DEFAULT false,
  overridden         boolean NOT NULL DEFAULT false,
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT case_form_field_values_unique UNIQUE (case_form_id, field_id)
);

COMMENT ON TABLE public.case_form_field_values IS 'Per-field value with provenance. One row per (case_form, field). Powers the AI confidence improvement loop (P4-6) — when overridden=true, the (original_value, corrected_value) delta is mined to surface low-accuracy pre-fill fields.';
COMMENT ON COLUMN public.case_form_field_values.filled_by IS 'Provenance of the value: ai (Pre-Fill Engine P2-1), system (default rule), employee (entered in form editor), specialist (Relopass ops), hr (HR contact).';

CREATE INDEX IF NOT EXISTS idx_case_form_field_values_case_form_id ON public.case_form_field_values(case_form_id);
CREATE INDEX IF NOT EXISTS idx_case_form_field_values_overridden   ON public.case_form_field_values(overridden) WHERE overridden = true;

-- ============================================================
-- TABLE: dossier_packages
-- A named bundle of case_forms exported as a single PDF.
-- Used for handoff to government authority or HR sign-off.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.dossier_packages (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id            uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  name               text NOT NULL,
  form_ids           jsonb NOT NULL DEFAULT '[]',   -- ordered array of case_forms.id (uuid strings)
  cover_page         boolean NOT NULL DEFAULT true,
  pdf_url            text,
  generated_at       timestamptz,
  created_by         uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.dossier_packages IS 'Named bundle of case_forms exported as a single PDF for handoff to authority or HR. Order of forms is preserved in form_ids jsonb.';
COMMENT ON COLUMN public.dossier_packages.form_ids IS 'Ordered JSON array of case_forms.id strings, e.g. ["uuid1","uuid2",...]. Ordering matters for the exported PDF.';

CREATE INDEX IF NOT EXISTS idx_dossier_packages_case_id  ON public.dossier_packages(case_id);
CREATE INDEX IF NOT EXISTS idx_dossier_packages_created_by ON public.dossier_packages(created_by);

-- ============================================================
-- updated_at TRIGGERS (moddatetime)
-- Matches platform_redesign_schema.sql convention.
-- ============================================================
CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.form_templates
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.case_forms
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.case_form_field_values
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE public.form_templates           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_forms               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_form_field_values   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dossier_packages         ENABLE ROW LEVEL SECURITY;

-- --- form_templates: catalog, public read for authenticated; admin write ---
DROP POLICY IF EXISTS form_templates_select_authenticated ON public.form_templates;
CREATE POLICY form_templates_select_authenticated ON public.form_templates
  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS form_templates_admin_write ON public.form_templates;
CREATE POLICY form_templates_admin_write ON public.form_templates
  FOR ALL USING (public.my_role() = 'admin')
  WITH CHECK (public.my_role() = 'admin');

-- --- case_forms: case-scoped (employee on case OR HR in same company) ---
-- Uses public.my_role() / public.my_company_id() helpers (live in public schema,
-- not auth — Supabase migration apply rewrote them from the source file).
DROP POLICY IF EXISTS case_forms_via_case ON public.case_forms;
CREATE POLICY case_forms_via_case ON public.case_forms FOR ALL
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

-- --- case_form_field_values: scope through the parent case_form ---
DROP POLICY IF EXISTS case_form_field_values_via_case ON public.case_form_field_values;
CREATE POLICY case_form_field_values_via_case ON public.case_form_field_values FOR ALL
  USING (case_form_id IN (
    SELECT cf.id FROM public.case_forms cf
    JOIN public.cases c ON c.id = cf.case_id
    WHERE c.employee_id = (SELECT auth.uid())
       OR (c.company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ))
  WITH CHECK (case_form_id IN (
    SELECT cf.id FROM public.case_forms cf
    JOIN public.cases c ON c.id = cf.case_id
    WHERE c.employee_id = (SELECT auth.uid())
       OR (c.company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ));

-- --- dossier_packages: case-scoped ---
DROP POLICY IF EXISTS dossier_packages_via_case ON public.dossier_packages;
CREATE POLICY dossier_packages_via_case ON public.dossier_packages FOR ALL
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

-- ============================================================
-- END OF MIGRATION
-- ============================================================
-- To apply: supabase db push
-- Regenerate types: supabase gen types typescript --linked > frontend/src/types/supabase.ts
-- (or run from backend if types live there — confirm with reviewer)
-- ============================================================
