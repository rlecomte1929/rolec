-- Auto-fill vertical slice — foundation schema for form prefill provenance,
-- form-template source language, and prefilled-document registration.
--
-- Additive, idempotent columns on THREE existing tables. No new tables are
-- created here, so no new RLS/policy/REVOKE is required (the CLAUDE.md hard
-- gate applies to NEW public tables only) — form_templates,
-- case_form_field_values and case_form_documents already carry RLS + policies,
-- which cover these new columns.
--
-- Do NOT apply this to production via MCP. Commit the file and let the normal
-- migrate flow apply + reconcile the ledger (CLAUDE.md migration discipline).
--
-- Columns added:
--   form_templates.source_language   — official language of the form's labels
--   case_form_field_values.source    — provenance of a prefilled value
--   case_form_documents.doc_kind     — kind of stored document
--   case_form_documents.fill_report  — per-field fill-report snapshot (jsonb)

-- ---------------------------------------------------------------------------
-- 1. form_templates.source_language
--    The language the official form / its labels are issued in. Drives the
--    dossier "show in English" toggle: when source_language != 'en', labels
--    (never identifier VALUES) are translated for comprehension. Default 'en'
--    so existing rows are unaffected; corridor seeds set 'nb', 'fr', etc.
-- ---------------------------------------------------------------------------
ALTER TABLE public.form_templates
  ADD COLUMN IF NOT EXISTS source_language text NOT NULL DEFAULT 'en';

COMMENT ON COLUMN public.form_templates.source_language IS
  'ISO 639-1 code of the language the official form/labels are issued in (e.g. ''en'', ''nb'', ''fr'', ''de''). Drives the dossier label-translation toggle; identifier VALUES are never translated.';

-- ---------------------------------------------------------------------------
-- 2. case_form_field_values.source
--    Provenance of a prefilled value, finer-grained than filled_by. Lets the
--    UI show a per-field source badge (intake / passport-OCR / prior form) and
--    the accuracy loop mine low-quality sources. Nullable: existing rows and
--    manually-entered values may carry no source. filled_by stays the coarse
--    ACTOR (ai/system/employee/...); source is the DATA ORIGIN.
-- ---------------------------------------------------------------------------
ALTER TABLE public.case_form_field_values
  ADD COLUMN IF NOT EXISTS source text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_form_field_values_source_chk'
  ) THEN
    ALTER TABLE public.case_form_field_values
      ADD CONSTRAINT case_form_field_values_source_chk
      CHECK (
        source IS NULL OR source IN (
          'intake_profile', 'contract', 'banking',
          'passport_ocr', 'prior_form',
          'authority_lookup', 'ai_inference',
          'manual', 'system'
        )
      );
  END IF;
END $$;

COMMENT ON COLUMN public.case_form_field_values.source IS
  'Data origin of the value: intake_profile | contract | banking | passport_ocr | prior_form | authority_lookup | ai_inference | manual | system. Nullable. Complements filled_by (the actor).';

-- ---------------------------------------------------------------------------
-- 3. case_form_documents.doc_kind + fill_report
--    doc_kind distinguishes a registered prefilled data-sheet ('prefilled')
--    from an uploaded / ad-hoc document. fill_report stores the per-field fill
--    snapshot (filled/blank/warning + source + confidence) captured at
--    registration, so the dossier can show what was auto-filled without
--    recomputing. Both nullable for legacy rows.
-- ---------------------------------------------------------------------------
ALTER TABLE public.case_form_documents
  ADD COLUMN IF NOT EXISTS doc_kind text;

ALTER TABLE public.case_form_documents
  ADD COLUMN IF NOT EXISTS fill_report jsonb;

COMMENT ON COLUMN public.case_form_documents.doc_kind IS
  'Kind of stored document, e.g. ''prefilled'' (a registered pre-filled data-sheet/form), ''uploaded'', ''adhoc''. Nullable for legacy rows.';

COMMENT ON COLUMN public.case_form_documents.fill_report IS
  'JSON snapshot of the per-field fill report at registration time (field, value/status, source, confidence). Nullable.';
