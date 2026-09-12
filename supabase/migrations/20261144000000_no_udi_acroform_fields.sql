-- ---------------------------------------------------------------------------
-- Seed form_field_mappings for the Norwegian UDI AcroForms — form-fill Build A,
-- the NO corridor's first fillable government forms (after FR CERFA #2286 and
-- ES EX-17). Blank AcroForms verified with pypdf.get_fields(); PDF fixtures and
-- <slug>_acroform_fields.json committed under docs/form-autofill/artifacts/.
--
-- GP-7028 (application for a permit for residence or work) is the omnibus
-- first-permit application: 232 named fields (166 /Tx, 66 /Btn). Its SHA-256
-- (a75786d22f4c1bb3284e42667b2f4456167e2b2fd4250c1b3df40a2a0fc2196f) matches the
-- claimed capture hash. GP-7116 (employment certificate EEA/EFTA) and the offer
-- of employment are the employer companion forms; the declaration of
-- relationship is the family-immigration form.
--
-- Seeds ONLY the plain-text (/Tx) fields that map 1:1 to a scalar
-- imm_employee_profiles vault column (the same discipline as the FR/ES seeds).
-- Deferred to a follow-up (need pipeline layers the fill does not have here):
--   * every /Btn radio/checkbox group (gender, marital status, permit type,
--     yes/no questions) — a value->button layer, as for FR/ES;
--   * address blocks — the vault stores current_address/employer_address as
--     jsonb, not a flat string, and the forms split them across many boxes;
--   * second-person / family-member / reference blocks on GP-7028 (…_2 / …_3),
--     which are other people, not the employee vault.
--
-- NOTE (scope): these form_ids are NOT yet in FILLABLE_FORM_IDS and no template
-- is uploaded to the form-templates bucket, so they are seeded but not offered
-- yet — the same staging the FR/ES forms went through. Wiring FILLABLE_FORM_IDS,
-- uploading the template, adding these to scripts/seed_prod_parity_manifest.json
-- (+ its locked test) and the /Btn choice rows are the follow-ups.
--
-- Applies to the NO corridor. Idempotent: NO_* rows removed before insert.
-- ---------------------------------------------------------------------------

BEGIN;

DELETE FROM public.form_field_mappings
 WHERE form_id IN ('NO_gp7028_v2024', 'NO_declaration_of_relationship_v2024', 'NO_gp7116_v2024', 'NO_offer_of_employment_v2024');

INSERT INTO public.form_field_mappings
  (form_id, form_name, corridor_to, visa_type,
   form_field_id, form_field_label, vault_field_path, format_rule, exact_match_required)
VALUES
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Family name', 'Family name (surname)', 'legal_last_name', 'name_normalise', TRUE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'First name', 'First name(s)', 'legal_first_name', 'name_normalise', TRUE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Middle name', 'Middle name', 'middle_names', 'name_normalise', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Date of birth daymonthyear', 'Date of birth (day/month/year)', 'date_of_birth', 'dd/mm/yyyy', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Place of birth', 'Place of birth', 'place_of_birth', 'name_normalise', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Citizenship specify all', 'Citizenship (specify all)', 'nationality', 'uppercase', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Employer company name or host family', 'Employer / company name or host family', 'employer_name', 'name_normalise', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Company registration number', 'Company registration number', 'employer_reg_number', NULL, FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Type of work job title or key task', 'Type of work / job title or key task', 'job_title', 'name_normalise', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Accomplished degree', 'Accomplished degree', 'highest_qualification', 'name_normalise', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Place of studyeducational institution', 'Place of study / educational institution', 'institution', 'name_normalise', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Travel / identity document number', 'Travel / identity document number', 'passport_number', 'passport_format', TRUE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Valid until ddmmyy', 'Travel document valid until', 'passport_expiry', 'dd/mm/yyyy', FALSE),
  ('NO_gp7028_v2024', 'Norway — Application for a residence/work permit (UDI GP-7028)', 'NO', 'work',
     'Country of issue', 'Travel document country of issue', 'passport_country', 'uppercase', FALSE),
  ('NO_declaration_of_relationship_v2024', 'Norway — Declaration of relationship (UDI, family immigration)', 'NO', 'family',
     'Family name', 'Family name (declarant / applicant)', 'legal_last_name', 'name_normalise', TRUE),
  ('NO_declaration_of_relationship_v2024', 'Norway — Declaration of relationship (UDI, family immigration)', 'NO', 'family',
     'First name', 'First name (declarant / applicant)', 'legal_first_name', 'name_normalise', TRUE),
  ('NO_declaration_of_relationship_v2024', 'Norway — Declaration of relationship (UDI, family immigration)', 'NO', 'family',
     'Date of birth ddmmyyyy', 'Date of birth (dd/mm/yyyy)', 'date_of_birth', 'dd/mm/yyyy', FALSE),
  ('NO_declaration_of_relationship_v2024', 'Norway — Declaration of relationship (UDI, family immigration)', 'NO', 'family',
     'Date of birth ddmmyyyy_2', 'Partner''s date of birth (dd/mm/yyyy)', 'spouse_dob', 'dd/mm/yyyy', FALSE),
  ('NO_gp7116_v2024', 'Norway — Employment certificate EEA/EFTA (UDI GP-7116)', 'NO', 'work',
     'Family name', 'Family name (employee)', 'legal_last_name', 'name_normalise', TRUE),
  ('NO_gp7116_v2024', 'Norway — Employment certificate EEA/EFTA (UDI GP-7116)', 'NO', 'work',
     'First name', 'First name (employee)', 'legal_first_name', 'name_normalise', TRUE),
  ('NO_gp7116_v2024', 'Norway — Employment certificate EEA/EFTA (UDI GP-7116)', 'NO', 'work',
     'Date of birth', 'Date of birth', 'date_of_birth', 'dd/mm/yyyy', FALSE),
  ('NO_gp7116_v2024', 'Norway — Employment certificate EEA/EFTA (UDI GP-7116)', 'NO', 'work',
     'Citizenship', 'Citizenship', 'nationality', 'uppercase', FALSE),
  ('NO_gp7116_v2024', 'Norway — Employment certificate EEA/EFTA (UDI GP-7116)', 'NO', 'work',
     'Name of enterprise responsible employer', 'Name of enterprise / responsible employer', 'employer_name', 'name_normalise', FALSE),
  ('NO_gp7116_v2024', 'Norway — Employment certificate EEA/EFTA (UDI GP-7116)', 'NO', 'work',
     'Organisation number', 'Organisation number', 'employer_reg_number', NULL, FALSE),
  ('NO_gp7116_v2024', 'Norway — Employment certificate EEA/EFTA (UDI GP-7116)', 'NO', 'work',
     'The person mentioned in section 1 is employed in the position of', 'Position held', 'job_title', 'name_normalise', FALSE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'Family name', 'Family name (employee)', 'legal_last_name', 'name_normalise', TRUE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'First name', 'First name (employee)', 'legal_first_name', 'name_normalise', TRUE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'Middle name', 'Middle name (employee)', 'middle_names', 'name_normalise', FALSE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'Date of birth daymonthyear', 'Date of birth (day/month/year)', 'date_of_birth', 'dd/mm/yyyy', FALSE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'Nationality', 'Nationality', 'nationality', 'uppercase', FALSE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'Responsible employer name of firm', 'Responsible employer / name of firm', 'employer_name', 'name_normalise', FALSE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'Organisation number', 'Organisation number', 'employer_reg_number', NULL, FALSE),
  ('NO_offer_of_employment_v2024', 'Norway — Offer of employment (UDI)', 'NO', 'work',
     'jobtitle', 'Job title', 'job_title', 'name_normalise', FALSE);

COMMIT;
