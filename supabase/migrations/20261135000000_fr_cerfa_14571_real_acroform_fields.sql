-- ---------------------------------------------------------------------------
-- Re-seed FR_cerfa_14571_v2024 form_field_mappings against the REAL AcroForm.
--
-- The original IMM-11 seed (20260605800000_imm11_form_field_mappings_seed.sql)
-- used French field ids (nom, prenoms, date_naissance, ...) that DO NOT EXIST in
-- the real form: docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md proved the
-- fillable France-Visas long-stay form (ls_14571-05_fr_09, 172 named fields) uses
-- semantic English AcroForm names (applicantSurname, travelDocNumber, ...). With
-- the old ids, fill_acroform() wrote nothing (zero overlap) — the fill report's
-- reconcile step would flag every field STATUS_NOT_IN_PDF.
--
-- This replaces those 12 fictional rows with the real AcroForm field names, taken
-- from docs/form-autofill/artifacts/fr_cerfa_14571-05_acroform_fields.json, mapped
-- to the imm_employee_profiles vault columns the fact dictionary now governs
-- (backend/app/services/fact_dictionary.py — Build B). Only the plain text (/Tx)
-- fields that map to a governed vault path are seeded here; the gender and marital-
-- status radio-button groups (applicantGenderM/F/Other, applicantMaritalCEL/MAR/…)
-- are /Btn export-value fields and need a value→button layer the fill pipeline does
-- not yet have — they are a deliberate follow-up, not an omission by accident.
--
-- form_id is kept stable (FR_cerfa_14571_v2024); the fill pipeline downloads the
-- template as {form_id}.pdf from the form-templates bucket, so the real France-Visas
-- *05 PDF is uploaded under that name (a separate, browser-only step — France-Visas
-- 403s non-browser fetchers). EDITION CAVEAT (Romain's call, per the feasibility
-- doc §5): service-public publishes *06 (flattened, unfillable); France-Visas
-- publishes *05 (fillable). These names are the *05 edition — the only fillable one.
--
-- Applies only to non-EEA → FR applicants (a long-stay visa); EEA → FR (incl. DE→FR)
-- has no visa form and uses the data sheet. Idempotent: FR rows removed before insert.
-- ---------------------------------------------------------------------------

BEGIN;

DELETE FROM public.form_field_mappings
 WHERE form_id = 'FR_cerfa_14571_v2024';

INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path, format_rule, exact_match_required)
VALUES
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'applicantSurname',       'Surname (family name)',          'legal_last_name',      'name_normalise',  TRUE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'applicantFirstname',     'First name(s)',                  'legal_first_name',     'name_normalise',  TRUE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'applicantDateOfBirth',   'Date of birth',                  'date_of_birth',        'dd/mm/yyyy',      FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'applicantPlaceOfBirth',  'Place of birth',                 'place_of_birth',       'name_normalise',  FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'applicantNationality',   'Current nationality',            'nationality',          'uppercase',       FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'travelDocNumber',        'Travel document number',         'passport_number',      'passport_format', TRUE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'travelDocDateOfIssue',   'Travel document date of issue',  'passport_issue_date',  'dd/mm/yyyy',      FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'travelDocValidUntil',    'Travel document valid until',    'passport_expiry',      'dd/mm/yyyy',      FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*05, France-Visas)', 'FR', 'long_stay',
     'applicantOccupation',    'Current occupation',             'job_title',            'name_normalise',  FALSE);

COMMIT;
