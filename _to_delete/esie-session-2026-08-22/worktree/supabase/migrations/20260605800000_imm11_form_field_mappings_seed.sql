-- ---------------------------------------------------------------------------
-- IMM-11 — Seed form_field_mappings for the two reference immigration forms:
--   * Germany EU Blue Card application   (DE_blue_card_v2024,   corridor DE / blue_card)
--   * France long-stay visa CERFA 14571  (FR_cerfa_14571_v2024, corridor FR / long_stay)
--
-- The form_field_mappings table (RLS-enabled) is created by IMM-01
-- (20260518120000_immigration_core_tables.sql). This migration only seeds rows.
--
-- vault_field_path values are column names on public.imm_employee_profiles.
-- Idempotent: existing rows for these two form_ids are removed before re-insert.
-- ---------------------------------------------------------------------------

BEGIN;

DELETE FROM public.form_field_mappings
 WHERE form_id IN ('DE_blue_card_v2024', 'FR_cerfa_14571_v2024');

-- --- Germany — EU Blue Card application -------------------------------------
INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path, format_rule, exact_match_required)
VALUES
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'family_name',            'Family name (surname)',     'legal_last_name',       'name_normalise', TRUE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'given_names',            'Given names',               'legal_first_name',      'name_normalise', TRUE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'date_of_birth',          'Date of birth',             'date_of_birth',         'dd/mm/yyyy',     FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'place_of_birth',         'Place of birth',            'place_of_birth',        'name_normalise', FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'nationality',            'Nationality',               'nationality',           'uppercase',      FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'gender',                 'Gender',                    'gender',                NULL,             FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'passport_number',        'Passport number',           'passport_number',       'passport_format', TRUE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'passport_issue_date',    'Passport date of issue',    'passport_issue_date',   'dd/mm/yyyy',     FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'passport_expiry',        'Passport date of expiry',   'passport_expiry',       'dd/mm/yyyy',     FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'passport_country',       'Passport issuing country',  'passport_country',      'uppercase',      FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'marital_status',         'Marital status',            'marital_status',        NULL,             FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'employer_name',          'Employer name',             'employer_name',         'name_normalise', FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'job_title',              'Job title',                 'job_title',             'name_normalise', FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'gross_annual_salary',    'Gross annual salary',       'salary_amount',         NULL,             FALSE),
  ('DE_blue_card_v2024', 'Germany — EU Blue Card application', 'DE', 'blue_card',
     'employment_start_date',  'Employment start date',     'employment_start_date', 'dd/mm/yyyy',     FALSE);

-- --- France — Long-stay visa CERFA 14571*09 ---------------------------------
INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path, format_rule, exact_match_required)
VALUES
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'nom',                    'Nom (surname)',                  'legal_last_name',     'name_normalise', TRUE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'prenoms',                'Prenoms (given names)',          'legal_first_name',    'name_normalise', TRUE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'date_naissance',         'Date de naissance',              'date_of_birth',       'dd/mm/yyyy',     FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'lieu_naissance',         'Lieu de naissance',              'place_of_birth',      'name_normalise', FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'nationalite',            'Nationalite',                    'nationality',         'uppercase',      FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'sexe',                   'Sexe',                           'gender',              NULL,             FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'numero_passeport',       'Numero de passeport',            'passport_number',     'passport_format', TRUE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'date_delivrance',        'Date de delivrance du passeport','passport_issue_date', 'dd/mm/yyyy',     FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'date_expiration',        'Date d''expiration du passeport','passport_expiry',     'dd/mm/yyyy',     FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'situation_familiale',    'Situation familiale',            'marital_status',      NULL,             FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'profession',             'Profession',                     'job_title',           'name_normalise', FALSE),
  ('FR_cerfa_14571_v2024', 'France — Long-stay visa application (CERFA 14571*09)', 'FR', 'long_stay',
     'employeur',              'Employeur',                      'employer_name',       'name_normalise', FALSE);

COMMIT;
