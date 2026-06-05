-- ============================================================
-- SEED — GREAT BRITAIN (GB) FORM TEMPLATE SET — Skilled Worker route
-- Date: 2026-06-10
--
-- Adds the second destination corridor (after Norway) to the
-- public.form_templates catalog that powers the Trigger Engine
-- (trigger_engine.fire_roadmap_events) -> case_forms -> roadmap/dossier.
--
-- Canonical destination code: 'GB' (ISO 3166-1 alpha-2, and what the
-- platform-v2 intake stores). The legacy frontend/src/utils/countries.ts
-- list uses 'UK'; that older path is out of scope here.
--
-- Event taxonomy (matches the Norway set + trigger_engine._derive_events):
--   roadmap.destination_confirmed — destination + visa type known
--   roadmap.profile_completed     — family composition known
--   roadmap.arrival_confirmed     — employee has arrived
--
-- visa_type for a work relocation resolves to 'skilled_worker'
-- (trigger_engine._purpose_to_visa_type('work')). So a work case fires
-- the four destination_confirmed forms below (SW-VISA, COS, NINO, PAYE).
--
-- Caveats (same as the Norway seed): field rosters are STARTER SETS
-- (6-10 representative fields), not the full official roster; prefill_source
-- paths follow the existing dotted convention and can be tuned in the admin
-- UI; original_pdf_url is NULL pending PDF upload. Treat as draft until
-- ops/legal review each form against the official source.
--
-- Idempotent via ON CONFLICT (code, version) DO NOTHING.
-- ============================================================

-- SW-VISA · Skilled Worker visa (main work route)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'SW-VISA',
  'Skilled Worker visa application',
  'GB',
  'UKVI',
  'UK Visas and Immigration (Home Office)',
  'work_permit',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"nationality","label":"Nationality (ISO)","type":"text","required":true,"prefill_source":"profile.nationality","requires_original":false,"position":3},
    {"id":"passport_number","label":"Passport number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":4},
    {"id":"passport_expiry","label":"Passport expiry date","type":"date","required":true,"prefill_source":"profile.passport_expiry","requires_original":false,"position":5},
    {"id":"cos_reference","label":"Certificate of Sponsorship reference","type":"text","required":true,"prefill_source":"contract.cos_reference","requires_original":false,"position":6},
    {"id":"employer_name","label":"Sponsoring employer","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":7},
    {"id":"job_title","label":"Job title (SOC code role)","type":"text","required":true,"prefill_source":"contract.job_title","requires_original":false,"position":8},
    {"id":"salary_amount","label":"Gross annual salary (GBP)","type":"number","required":true,"prefill_source":"contract.salary_amount_gbp","requires_original":false,"position":9},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":10}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"GB","visa_type":"skilled_worker"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":100}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- COS · Certificate of Sponsorship (issued by employer before the visa)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'COS',
  'Certificate of Sponsorship request',
  'GB',
  'UKVI',
  'UK Visas and Immigration (Home Office)',
  'work_permit',
  '1.0.0',
  '[
    {"id":"employee_full_name","label":"Employee full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"employer_name","label":"Sponsor (employer) name","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":2},
    {"id":"sponsor_licence_number","label":"Sponsor licence number","type":"text","required":true,"prefill_source":"contract.sponsor_licence_number","requires_original":false,"position":3},
    {"id":"job_title","label":"Job title","type":"text","required":true,"prefill_source":"contract.job_title","requires_original":false,"position":4},
    {"id":"soc_code","label":"SOC occupation code","type":"text","required":true,"prefill_source":"contract.soc_code","requires_original":false,"position":5},
    {"id":"salary_amount","label":"Gross annual salary (GBP)","type":"number","required":true,"prefill_source":"contract.salary_amount_gbp","requires_original":false,"position":6},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":7}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"GB","visa_type":"skilled_worker"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":110}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- NINO · National Insurance number registration
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'NINO',
  'National Insurance number application',
  'GB',
  'DWP',
  'Department for Work and Pensions',
  'banking',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"uk_address","label":"UK residential address","type":"text","required":true,"prefill_source":"profile.destination_address","requires_original":false,"position":3},
    {"id":"brp_number","label":"BRP number (if issued)","type":"text","required":false,"prefill_source":"profile.brp_number","requires_original":false,"position":4},
    {"id":"employer_name","label":"Employer name","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":5},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":6}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"GB"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":80}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- HMRC-PAYE · Starter checklist for PAYE / tax code
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'HMRC-PAYE',
  'HMRC starter checklist (PAYE)',
  'GB',
  'HMRC',
  'HM Revenue & Customs',
  'tax',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"nino","label":"National Insurance number (if known)","type":"text","required":false,"prefill_source":"profile.nino","requires_original":false,"position":3},
    {"id":"uk_address","label":"UK residential address","type":"text","required":true,"prefill_source":"profile.destination_address","requires_original":false,"position":4},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":5},
    {"id":"employer_paye_ref","label":"Employer PAYE reference","type":"text","required":true,"prefill_source":"contract.employer_paye_ref","requires_original":false,"position":6}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"GB"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":70}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- BRP-COLLECT · Biometric Residence Permit collection (post-arrival)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'BRP-COLLECT',
  'Biometric Residence Permit collection',
  'GB',
  'UKVI',
  'UK Visas and Immigration (Home Office)',
  'registration',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"vignette_number","label":"Entry vignette number","type":"text","required":true,"prefill_source":"profile.vignette_number","requires_original":true,"position":2},
    {"id":"collection_location","label":"Collection Post Office / location","type":"text","required":true,"prefill_source":"profile.brp_collection_location","requires_original":false,"position":3},
    {"id":"uk_arrival_date","label":"UK arrival date","type":"date","required":true,"prefill_source":"arrival.actual_move_date","requires_original":false,"position":4},
    {"id":"passport_number","label":"Passport number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"GB"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":90}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- NHS-GP · GP (doctor) registration (post-arrival)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'NHS-GP',
  'NHS GP registration (GMS1)',
  'GB',
  'NHS',
  'National Health Service',
  'health',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"uk_address","label":"UK residential address","type":"text","required":true,"prefill_source":"profile.destination_address","requires_original":false,"position":3},
    {"id":"nhs_number","label":"NHS number (if known)","type":"text","required":false,"prefill_source":"profile.nhs_number","requires_original":false,"position":4},
    {"id":"previous_country","label":"Country travelled from","type":"text","required":true,"prefill_source":"profile.origin_country","requires_original":false,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"GB"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":60}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- COUNCIL-TAX · Council Tax registration (post-arrival)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'COUNCIL-TAX',
  'Council Tax registration',
  'GB',
  'LOCAL-AUTHORITY',
  'Local Authority',
  'tax',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"uk_address","label":"UK residential address","type":"text","required":true,"prefill_source":"profile.destination_address","requires_original":false,"position":2},
    {"id":"move_in_date","label":"Move-in date","type":"date","required":true,"prefill_source":"arrival.actual_move_date","requires_original":false,"position":3},
    {"id":"tenure","label":"Tenure","type":"select","required":true,"prefill_source":"profile.tenure","requires_original":false,"position":4,"options":["owner","tenant","other"]},
    {"id":"household_adults","label":"Number of adults in household","type":"number","required":true,"prefill_source":"family.adult_count","requires_original":false,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"GB"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":50}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- DEP-PARTNER · Dependant partner visa (family)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'DEP-PARTNER',
  'Dependant partner visa application',
  'GB',
  'UKVI',
  'UK Visas and Immigration (Home Office)',
  'family',
  '1.0.0',
  '[
    {"id":"partner_full_name","label":"Partner full legal name","type":"text","required":true,"prefill_source":"family.spouse.legal_full_name","requires_original":false,"position":1},
    {"id":"partner_date_of_birth","label":"Partner date of birth","type":"date","required":true,"prefill_source":"family.spouse.date_of_birth","requires_original":false,"position":2},
    {"id":"partner_nationality","label":"Partner nationality (ISO)","type":"text","required":true,"prefill_source":"family.spouse.nationality","requires_original":false,"position":3},
    {"id":"partner_passport_number","label":"Partner passport number","type":"text","required":true,"prefill_source":"family.spouse.passport_number","requires_original":true,"position":4},
    {"id":"relationship_date","label":"Date relationship began / marriage date","type":"date","required":true,"prefill_source":"family.marriage_date","requires_original":true,"position":5},
    {"id":"sponsor_full_name","label":"Sponsor (employee) full name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":6}
  ]'::jsonb,
  '[
    {"event":"roadmap.profile_completed","conditions":{"destination_country":"GB","has_spouse":true},"for_persons":["spouse"],"blocked_by_template_code":null,"priority":85}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- DEP-CHILD · Dependant child visa (family) — one per child
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'DEP-CHILD',
  'Dependant child visa application',
  'GB',
  'UKVI',
  'UK Visas and Immigration (Home Office)',
  'family',
  '1.0.0',
  '[
    {"id":"child_full_name","label":"Child full legal name","type":"text","required":true,"prefill_source":"person.legal_full_name","requires_original":false,"position":1},
    {"id":"child_date_of_birth","label":"Child date of birth","type":"date","required":true,"prefill_source":"person.date_of_birth","requires_original":false,"position":2},
    {"id":"child_nationality","label":"Child nationality (ISO)","type":"text","required":true,"prefill_source":"person.nationality","requires_original":false,"position":3},
    {"id":"child_passport_number","label":"Child passport number","type":"text","required":true,"prefill_source":"person.passport_number","requires_original":true,"position":4},
    {"id":"relationship_to_employee","label":"Relationship to employee","type":"select","required":true,"prefill_source":"person.relationship","requires_original":false,"position":5,"options":["biological_child","adopted_child","stepchild"]},
    {"id":"sponsor_full_name","label":"Sponsor (employee) full name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":6}
  ]'::jsonb,
  '[
    {"event":"roadmap.profile_completed","conditions":{"destination_country":"GB","has_children":true},"for_persons":["each_child"],"blocked_by_template_code":null,"priority":84}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;
