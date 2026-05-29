-- C1-01b · Seed migrations for rce.document_types + rce.authorities
--
-- Populates the lookup catalogs from the curated Notion sources:
--   * Document Types (17 codes) — Notion Document Types DB
--   * Authorities (≥25 entries) — R-07 authority dossier
--
-- Idempotency: ON CONFLICT (unique key) DO UPDATE — re-running the
-- migration on top of existing data produces zero duplicate rows. The
-- `updated_at` timestamp moves forward so the audit trail captures the
-- refresh, but no row is duplicated.
--
-- Adds two `source_url` columns (one per table) for provenance. The
-- value points back at the Notion page each row was authored from.
-- Required by C1-01b criterion 5.
--
-- Schema additions are minimal and additive (NULLable TEXT columns) so
-- the migration is safe to apply on an already-populated database.

-- ─────────────────────────────────────────────────────────────────────────────
-- Schema additions (additive, NULLable — safe on populated DBs)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE rce.document_types
  ADD COLUMN IF NOT EXISTS source_url TEXT;

ALTER TABLE rce.authorities
  ADD COLUMN IF NOT EXISTS source_url TEXT;

-- Authority uniqueness is by (name, country_iso3) — same name in two
-- countries (e.g. "Foreign Ministry") is intentionally allowed; same
-- name in the same country is a duplicate.
ALTER TABLE rce.authorities
  ADD CONSTRAINT authorities_name_country_unique
  UNIQUE (name, country_iso3);

-- ─────────────────────────────────────────────────────────────────────────────
-- DOCUMENT TYPES (17 codes from the Notion Document Types DB)
--
-- expected_fields_json carries the field-key set the corresponding C1-05
-- extraction agent emits. validator_pack stays NULL — populated by C1-05
-- agents at registration time.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO rce.document_types (code, expected_fields_json, source_url) VALUES
  ('PASSPORT_TD3', '{"fields":["surname","given_names","document_number","nationality_iso3","issuing_state_iso3","date_of_birth","sex","expiry_date","photo_bbox","signature_bbox","issuing_authority","endorsements"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('EU_NATIONAL_ID', '{"fields":["surname","given_names","document_number","nationality_iso3","issuing_state_iso3","date_of_birth","sex","expiry_date","photo_bbox"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('RESIDENCE_PERMIT_EU', '{"fields":["surname","given_names","document_number","nationality_iso3","issuing_state_iso3","date_of_birth","sex","expiry_date","validity_start","residence_purpose_code","permit_type","restrictions","work_authorization"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('EMPLOYMENT_CONTRACT', '{"fields":["employer_legal_name","employer_registry_id","position_title","position_isco_2008","gross_salary_annual","gross_salary_guaranteed_fixed_only_bool","contract_start_date","contract_duration_months","working_time_percent"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('PAYSLIP', '{"fields":["employer_name","employer_address","gross_monthly","net_monthly","tax_withheld","ytd_gross","pay_period_start","pay_period_end","derived_annual","locale"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('DIPLOMA_BACHELOR', '{"fields":["institution_name","institution_name_native","qualification_title","isced_level","award_date","field_of_study","country_iso3","recognized_in_anabin"],"isced_level_expected":6}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('DIPLOMA_MASTER', '{"fields":["institution_name","institution_name_native","qualification_title","isced_level","award_date","field_of_study","country_iso3","recognized_in_anabin"],"isced_level_expected":7}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('ANABIN_EVIDENCE', '{"fields":["institution_anabin_status","institution_match_url","qualification_anabin_match","statement_date"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('ZAB_STATEMENT_OF_COMPARABILITY', '{"fields":["statement_id","statement_date","qualification_compared_to","country_of_origin","recognized_isced_level"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('IT_EXPERIENCE_PORTFOLIO', '{"fields":["years_relevant_experience","employer_chain","role_summary","skills_evidenced"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('HEALTH_INSURANCE_PROOF', '{"fields":["insurer_name","policy_number","coverage_start","coverage_end","covered_persons"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('MARRIAGE_CERT', '{"fields":["surname_spouse_a","given_names_spouse_a","surname_spouse_b","given_names_spouse_b","maiden_surname_a","maiden_surname_b","marriage_date","marriage_country_iso3","authority_name"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('BIRTH_CERT', '{"fields":["surname","given_names","date_of_birth","country_iso3","mother_name","father_name","authority_name"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('FOSTER_CARE_ORDER', '{"fields":["child_surname","child_given_names","child_dob","guardian_surname","guardian_given_names","order_date","authority_name"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('CRIMINAL_RECORD', '{"fields":["surname","given_names","record_status","issuing_country_iso3","authority_name","statement_date"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('TAX_CERT', '{"fields":["taxpayer_name","tax_id","tax_year","gross_income","tax_paid","country_iso3","authority_name"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750'),

  ('HOUSING_LEASE', '{"fields":["tenant_name","landlord_name","property_address","lease_start","lease_end","monthly_rent","currency_iso3"]}'::jsonb,
   'https://www.notion.so/1a0265f08c6e4d48b0bc6c2b3aa52750')

ON CONFLICT (code) DO UPDATE
  SET expected_fields_json = EXCLUDED.expected_fields_json,
      source_url = EXCLUDED.source_url,
      updated_at = now();

-- ─────────────────────────────────────────────────────────────────────────────
-- AUTHORITIES (≥25 entries from R-07 dossier)
--
-- Country code 'XEU' = European Union (ISO-3 placeholder used by EUR-Lex
-- and other supranational bodies).
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO rce.authorities (name, country_iso3, jurisdiction, official_url, source_url) VALUES
  -- Norway
  ('UDI', 'NOR', 'national', 'https://www.udi.no',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Politiet', 'NOR', 'national', 'https://www.politiet.no',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Lovdata', 'NOR', 'national', 'https://lovdata.no',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Folkeregister', 'NOR', 'national', 'https://www.skatteetaten.no/en/person/national-registry',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('NAV', 'NOR', 'national', 'https://www.nav.no',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),

  -- Germany
  ('BAMF', 'DEU', 'national', 'https://www.bamf.de',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Make it in Germany', 'DEU', 'national', 'https://www.make-it-in-germany.com',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('anabin', 'DEU', 'national', 'https://anabin.kmk.org',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('ZAB', 'DEU', 'national', 'https://www.kmk.org/zab',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Bundesagentur für Arbeit', 'DEU', 'national', 'https://www.arbeitsagentur.de',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Gesetze-im-Internet', 'DEU', 'national', 'https://www.gesetze-im-internet.de',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('dejure.org', 'DEU', 'national', 'https://dejure.org',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('BGBl.', 'DEU', 'national', 'https://www.bgbl.de',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Bundesanzeiger', 'DEU', 'national', 'https://www.bundesanzeiger.de',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Munich KVR', 'DEU', 'local_munich', 'https://www.muenchen.de/rathaus/Stadtverwaltung/Kreisverwaltungsreferat',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Berlin LEA', 'DEU', 'local_berlin', 'https://www.berlin.de/einwanderung',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),

  -- European Union
  ('EUR-Lex', 'XEU', 'supranational', 'https://eur-lex.europa.eu',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),

  -- France
  ('Service-Public.fr', 'FRA', 'national', 'https://www.service-public.fr',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Légifrance', 'FRA', 'national', 'https://www.legifrance.gouv.fr',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('Préfecture de Paris', 'FRA', 'local_paris', 'https://www.prefecturedepolice.interieur.gouv.fr',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),

  -- India
  ('Passport Seva', 'IND', 'national', 'https://www.passportindia.gov.in',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('MEA Apostille', 'IND', 'national', 'https://www.mea.gov.in/apostille.htm',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('CBSE', 'IND', 'national', 'https://www.cbse.gov.in',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),

  -- United States
  ('U.S. Department of State', 'USA', 'national', 'https://travel.state.gov',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),

  -- International / supranational
  ('ICAO', 'XINT', 'international', 'https://www.icao.int',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee'),
  ('UNESCO', 'XINT', 'international', 'https://www.unesco.org',
   'https://www.notion.so/36d887c64d4881cb8dbbe8295f66a3ee')

ON CONFLICT (name, country_iso3) DO UPDATE
  SET jurisdiction = EXCLUDED.jurisdiction,
      official_url = EXCLUDED.official_url,
      source_url = EXCLUDED.source_url,
      updated_at = now();
