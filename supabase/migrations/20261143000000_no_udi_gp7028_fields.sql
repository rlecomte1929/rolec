-- ---------------------------------------------------------------------------
-- Seed form_field_mappings for Norway UDI GP7028 — the third real government
-- AcroForm after France-Visas CERFA (#2286) and Spain EX-17 / TIE.
--
-- Official source (udi.no English edition, last modified 2024-06-18):
--   https://www.udi.no/globalassets/global/skjemaer/application_-for_a_permit_for_residence_or_work_gp7028.pdf
-- Verified fillable: 232 named AcroForm fields (pypdf.get_fields). Fixture + raw
-- field dump: docs/form-autofill/artifacts/no_udi_gp7028.pdf and
-- docs/form-autofill/artifacts/no_udi_gp7028_acroform_fields.ndjson.
--
-- ONLY the governed-vault subset is mapped (~13 of 232). Study, criminal history,
-- travel-history rows, children rows, power of attorney, signatures, and contact
-- stay unmapped. Date of birth is a single /Tx field (not a day/month/year split).
-- Gender and marital status are single-radio groups (the ES EX-17 shape).
--
-- visa_type is skilled_worker only. GP7028 also serves family immigration — that
-- corridor is a follow-up, not seeded here.
--
-- Idempotent: deletes only this form_id's text + single_radio rows before insert
-- (never an unscoped WHERE form_id — that would wipe sibling kinds).
-- ---------------------------------------------------------------------------

BEGIN;

DELETE FROM public.form_field_mappings
 WHERE form_id = 'NO_udi_gp7028_v2024'
   AND field_kind IN ('text', 'single_radio');

INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path, format_rule, exact_match_required,
   field_kind, transform_spec)
VALUES
  -- text (/Tx) — applicant identity + skilled-worker employment
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Family name', 'Family name', 'legal_last_name', 'name_normalise', TRUE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'First name', 'First name', 'legal_first_name', 'name_normalise', TRUE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Date of birth daymonthyear', 'Date of birth (day/month/year)', 'date_of_birth', 'dd/mm/yyyy', FALSE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Place of birth', 'Place of birth', 'place_of_birth', 'name_normalise', FALSE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Citizenship specify all', 'Citizenship (specify all)', 'nationality', 'uppercase', FALSE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Travel / identity document number', 'Travel / identity document number', 'passport_number', 'passport_format', TRUE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Valid until ddmmyy', 'Valid until (dd/mm/yy)', 'passport_expiry', 'dd/mm/yyyy', FALSE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Country of issue', 'Country of issue', 'passport_country', 'uppercase', FALSE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Type of work job title or key task', 'Type of work (job title or key task)', 'job_title', 'name_normalise', FALSE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Employer company name or host family', 'Employer (company name or host family)', 'employer_name', 'name_normalise', FALSE, 'text', NULL),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Wage in NOK', 'Wage (in NOK)', 'salary_amount', NULL, FALSE, 'text', NULL),
  -- single_radio (/Btn) — real on-states from the NDJSON /_States_
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Gender', 'Gender', 'gender', NULL, FALSE, 'single_radio',
     '{"values":{"M":"/Male","F":"/Female"}}'),
  ('NO_udi_gp7028_v2024', 'Norway — Application for a permit for residence or work (UDI GP7028)', 'NO', 'skilled_worker',
     'Marital status group 1', 'Marital status', 'marital_status', NULL, FALSE, 'single_radio',
     '{"values":{"SINGLE":"/Single","MARRIED":"/Married / civil partner","COHABITANT":"/Cohabitant","SEPARATED":"/Separated","DIVORCED":"/Divorced","WIDOWED":"/Widow/widower"}}');

COMMIT;
