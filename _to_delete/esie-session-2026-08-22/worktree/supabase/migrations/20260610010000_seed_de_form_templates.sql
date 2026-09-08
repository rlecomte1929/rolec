-- ============================================================
-- SEED — GERMANY (DE) FORM TEMPLATE SET — Skilled Worker route
-- Date: 2026-06-10
--
-- Third destination corridor (after Norway and Great Britain). Seeds 9 DE
-- form_templates into the catalog that drives the trigger engine
-- (trigger_engine.fire_roadmap_events) -> case_forms -> roadmap/dossier.
--
-- Canonical destination code 'DE' (ISO + what platform-v2 intake stores).
-- Event taxonomy matches the NO/GB sets + trigger_engine._derive_events.
-- A work relocation resolves visa_type 'skilled_worker', so the four
-- destination_confirmed forms below fire for a work case.
--
-- Caveats (same as NO/GB seeds): starter field rosters; prefill_source paths
-- follow the dotted convention; original_pdf_url NULL pending upload. Treat as
-- draft until ops/legal review each form against the official source.
--
-- Idempotent via ON CONFLICT (code, version) DO NOTHING.
-- ============================================================

-- WORK-VISA-DE · National D-visa for employment (entry visa)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'WORK-VISA-DE',
  'National visa for employment (D-Visa)',
  'DE',
  'AUSWAERTIGES-AMT',
  'Federal Foreign Office (German mission)',
  'work_permit',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"nationality","label":"Nationality (ISO)","type":"text","required":true,"prefill_source":"profile.nationality","requires_original":false,"position":3},
    {"id":"passport_number","label":"Passport number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":4},
    {"id":"passport_expiry","label":"Passport expiry date","type":"date","required":true,"prefill_source":"profile.passport_expiry","requires_original":false,"position":5},
    {"id":"employer_name","label":"Employer in Germany","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":6},
    {"id":"job_title","label":"Job title","type":"text","required":true,"prefill_source":"contract.job_title","requires_original":false,"position":7},
    {"id":"salary_amount","label":"Gross annual salary (EUR)","type":"number","required":true,"prefill_source":"contract.salary_amount_eur","requires_original":false,"position":8},
    {"id":"qualification_recognition","label":"Recognised qualification reference","type":"text","required":false,"prefill_source":"profile.qualification_recognition_ref","requires_original":false,"position":9},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":10}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"DE","visa_type":"skilled_worker"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":100}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- BLUE-CARD · EU Blue Card / residence title for qualified employment
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'BLUE-CARD',
  'EU Blue Card / residence title (Aufenthaltstitel)',
  'DE',
  'AUSLAENDERBEHOERDE',
  'Auslaenderbehoerde (Immigration Office)',
  'work_permit',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"passport_number","label":"Passport number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":3},
    {"id":"employer_name","label":"Employer","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":4},
    {"id":"job_title","label":"Job title","type":"text","required":true,"prefill_source":"contract.job_title","requires_original":false,"position":5},
    {"id":"salary_amount","label":"Gross annual salary (EUR)","type":"number","required":true,"prefill_source":"contract.salary_amount_eur","requires_original":false,"position":6},
    {"id":"de_address","label":"German residential address","type":"text","required":false,"prefill_source":"profile.destination_address","requires_original":false,"position":7}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"DE","visa_type":"skilled_worker"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":110}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- STEUER-ID · Tax identification number
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'STEUER-ID',
  'Tax identification number (Steuerliche Identifikationsnummer)',
  'DE',
  'BZST',
  'Federal Central Tax Office (Bundeszentralamt fuer Steuern)',
  'tax',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"de_address","label":"German residential address","type":"text","required":true,"prefill_source":"profile.destination_address","requires_original":false,"position":3},
    {"id":"employer_name","label":"Employer name","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":4},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"DE"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":80}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- KRANKENV · Statutory health insurance enrolment
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'KRANKENV',
  'Statutory health insurance enrolment (Krankenversicherung)',
  'DE',
  'GKV',
  'Statutory Health Insurance (Gesetzliche Krankenversicherung)',
  'health',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"employer_name","label":"Employer name","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":3},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":4},
    {"id":"dependents_count","label":"Number of dependents to co-insure","type":"number","required":false,"prefill_source":"family.dependent_count","requires_original":false,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"DE"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":70}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- ANMELDUNG · Address registration (post-arrival)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'ANMELDUNG',
  'Address registration (Anmeldung beim Buergeramt)',
  'DE',
  'BUERGERAMT',
  'Buergeramt (Citizens Office)',
  'registration',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"de_address","label":"German residential address","type":"text","required":true,"prefill_source":"profile.destination_address","requires_original":false,"position":3},
    {"id":"move_in_date","label":"Move-in date (Einzugsdatum)","type":"date","required":true,"prefill_source":"arrival.actual_move_date","requires_original":false,"position":4},
    {"id":"landlord_confirmation","label":"Landlord confirmation (Wohnungsgeberbestaetigung)","type":"text","required":true,"prefill_source":"profile.landlord_confirmation_ref","requires_original":true,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"DE"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":90}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- BANK-DE · German bank account opening (post-arrival)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'BANK-DE',
  'German bank account opening (Girokonto)',
  'DE',
  'DE-BANK',
  'German retail bank',
  'banking',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"de_address","label":"German residential address (registered)","type":"text","required":true,"prefill_source":"profile.destination_address","requires_original":false,"position":2},
    {"id":"steuer_id","label":"Tax ID (Steuer-ID)","type":"text","required":false,"prefill_source":"profile.steuer_id","requires_original":false,"position":3},
    {"id":"employer_name","label":"Employer name","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":4},
    {"id":"anmeldung_ref","label":"Registration certificate (Meldebescheinigung) ref","type":"text","required":true,"prefill_source":"profile.anmeldung_ref","requires_original":true,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"DE"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":60}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- RESID-PERMIT-DE · Residence permit collection at the immigration office (post-arrival)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'RESID-PERMIT-DE',
  'Residence permit appointment (Auslaenderbehoerde)',
  'DE',
  'AUSLAENDERBEHOERDE',
  'Auslaenderbehoerde (Immigration Office)',
  'registration',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"passport_number","label":"Passport number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":2},
    {"id":"anmeldung_ref","label":"Registration certificate ref","type":"text","required":true,"prefill_source":"profile.anmeldung_ref","requires_original":true,"position":3},
    {"id":"biometric_photo","label":"Biometric photo provided","type":"select","required":true,"prefill_source":"profile.biometric_photo_status","requires_original":false,"position":4,"options":["yes","no"]},
    {"id":"de_arrival_date","label":"Germany arrival date","type":"date","required":true,"prefill_source":"arrival.actual_move_date","requires_original":false,"position":5}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"DE"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":50}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- FAM-SPOUSE · Family reunion visa (spouse)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'FAM-SPOUSE',
  'Family reunion visa - spouse (Familiennachzug)',
  'DE',
  'AUSLAENDERBEHOERDE',
  'Auslaenderbehoerde (Immigration Office)',
  'family',
  '1.0.0',
  '[
    {"id":"spouse_full_name","label":"Spouse full legal name","type":"text","required":true,"prefill_source":"family.spouse.legal_full_name","requires_original":false,"position":1},
    {"id":"spouse_date_of_birth","label":"Spouse date of birth","type":"date","required":true,"prefill_source":"family.spouse.date_of_birth","requires_original":false,"position":2},
    {"id":"spouse_nationality","label":"Spouse nationality (ISO)","type":"text","required":true,"prefill_source":"family.spouse.nationality","requires_original":false,"position":3},
    {"id":"spouse_passport_number","label":"Spouse passport number","type":"text","required":true,"prefill_source":"family.spouse.passport_number","requires_original":true,"position":4},
    {"id":"marriage_date","label":"Date of marriage","type":"date","required":true,"prefill_source":"family.marriage_date","requires_original":true,"position":5},
    {"id":"language_certificate","label":"A1 German language certificate ref","type":"text","required":false,"prefill_source":"family.spouse.language_certificate_ref","requires_original":false,"position":6},
    {"id":"sponsor_full_name","label":"Sponsor (employee) full name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":7}
  ]'::jsonb,
  '[
    {"event":"roadmap.profile_completed","conditions":{"destination_country":"DE","has_spouse":true},"for_persons":["spouse"],"blocked_by_template_code":null,"priority":85}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- FAM-CHILD · Family reunion visa (minor child) — one per child
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'FAM-CHILD',
  'Family reunion visa - minor child (Familiennachzug)',
  'DE',
  'AUSLAENDERBEHOERDE',
  'Auslaenderbehoerde (Immigration Office)',
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
    {"event":"roadmap.profile_completed","conditions":{"destination_country":"DE","has_children":true},"for_persons":["each_child"],"blocked_by_template_code":null,"priority":84}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;
