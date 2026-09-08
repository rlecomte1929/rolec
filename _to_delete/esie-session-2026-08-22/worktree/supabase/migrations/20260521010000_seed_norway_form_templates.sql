-- ============================================================
-- [P1-4] SEED — NORWAY FORM TEMPLATE SET (8 official forms)
-- Date: 2026-05-21
--
-- Seeds the public.form_templates catalog (created in P1-1) with 8 Norway
-- forms covering work permit, family immigration, address registration,
-- D-number, health insurance, tax card, and bank/payroll. Powers the
-- happy path for the Trigger Engine (P1-3).
--
-- Two changes:
--   1. ALTER trigger_rules DEFAULT '{}' → '[]'
--      The P1-3 spec iterates over trigger_rules as an array. The original
--      column default (object) doesn't match the consumer's expectation.
--      Cleanest fix is to change the default now, before any rows exist
--      that use the empty-object form.
--   2. INSERT 8 templates, idempotent via ON CONFLICT (code, version).
--
-- Caveats for the reviewer:
--   - Field rosters are STARTER SETS (6-10 representative fields per form),
--     not the full official roster. The complete set lands once the
--     P1-2B Fields editor exists and ops/legal can review each form
--     against the official PDF. Treat anything here as draft until verified.
--   - prefill_source paths use a sensible dotted convention
--     (profile.legal_first_name, contract.employer_name, etc.). Concrete
--     paths will be locked in by P2-1 Pre-Fill Engine and are easy to
--     update via the admin UI shipped in P1-2A.
--   - original_pdf_url is NULL on all 8 — PDF upload to Supabase Storage
--     is deferred to P1-2B.
--   - Event taxonomy used: roadmap.destination_confirmed,
--     roadmap.profile_completed, roadmap.arrival_confirmed. The first two
--     are in the P1-3 spec; `roadmap.arrival_confirmed` is added here for
--     post-arrival forms (Folkeregisteret address reg, health insurance,
--     tax card) and should be wired up in P1-3 alongside the others.
--   - Blocking deps (HELFO-1 / RF-1209 blocked_by GP-7-04) are encoded in
--     the trigger_rules as `blocked_by_template_code`. The Trigger Engine
--     resolves these to actual CaseForm IDs at creation time.
-- ============================================================

-- ---- 1. Align trigger_rules default with array shape ----
ALTER TABLE public.form_templates
  ALTER COLUMN trigger_rules SET DEFAULT '[]'::jsonb;

-- ---- 2. Seed 8 Norway form templates (idempotent) ----

-- UTL-2011 · Work permit (skilled worker)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'UTL-2011',
  'Søknad om oppholdstillatelse for arbeid (faglært)',
  'NO',
  'UDI',
  'Utlendingsdirektoratet (Norwegian Directorate of Immigration)',
  'work_permit',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"nationality","label":"Nationality (ISO)","type":"text","required":true,"prefill_source":"profile.nationality","requires_original":false,"position":3},
    {"id":"passport_number","label":"Passport number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":4},
    {"id":"passport_expiry","label":"Passport expiry date","type":"date","required":true,"prefill_source":"profile.passport_expiry","requires_original":false,"position":5},
    {"id":"employer_name","label":"Employer in Norway","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":6},
    {"id":"employer_org_number","label":"Employer org. number","type":"text","required":true,"prefill_source":"contract.employer_org_number","requires_original":false,"position":7},
    {"id":"job_title","label":"Job title","type":"text","required":true,"prefill_source":"contract.job_title","requires_original":false,"position":8},
    {"id":"salary_amount","label":"Gross annual salary (NOK)","type":"number","required":true,"prefill_source":"contract.salary_amount_nok","requires_original":false,"position":9},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":10}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"NO","visa_type":"skilled_worker"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":100}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- UTL-2011F · Family immigration (spouse)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'UTL-2011F',
  'Søknad om familieinnvandring (ektefelle)',
  'NO',
  'UDI',
  'Utlendingsdirektoratet (Norwegian Directorate of Immigration)',
  'family',
  '1.0.0',
  '[
    {"id":"spouse_full_name","label":"Spouse full legal name","type":"text","required":true,"prefill_source":"family.spouse.legal_full_name","requires_original":false,"position":1},
    {"id":"spouse_date_of_birth","label":"Spouse date of birth","type":"date","required":true,"prefill_source":"family.spouse.date_of_birth","requires_original":false,"position":2},
    {"id":"spouse_nationality","label":"Spouse nationality (ISO)","type":"text","required":true,"prefill_source":"family.spouse.nationality","requires_original":false,"position":3},
    {"id":"spouse_passport_number","label":"Spouse passport number","type":"text","required":true,"prefill_source":"family.spouse.passport_number","requires_original":true,"position":4},
    {"id":"spouse_passport_expiry","label":"Spouse passport expiry","type":"date","required":true,"prefill_source":"family.spouse.passport_expiry","requires_original":false,"position":5},
    {"id":"marriage_date","label":"Date of marriage","type":"date","required":true,"prefill_source":"family.marriage_date","requires_original":true,"position":6},
    {"id":"marriage_place","label":"Place of marriage","type":"text","required":true,"prefill_source":"family.marriage_place","requires_original":false,"position":7},
    {"id":"sponsor_full_name","label":"Sponsor (employee) full name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":8}
  ]'::jsonb,
  '[
    {"event":"roadmap.profile_completed","conditions":{"destination_country":"NO","has_spouse":true},"for_persons":["spouse"],"blocked_by_template_code":null,"priority":90}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- UTL-2011B · Family immigration (minor child) — one per child
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'UTL-2011B',
  'Søknad om familieinnvandring (mindreårig barn)',
  'NO',
  'UDI',
  'Utlendingsdirektoratet (Norwegian Directorate of Immigration)',
  'family',
  '1.0.0',
  '[
    {"id":"child_full_name","label":"Child full legal name","type":"text","required":true,"prefill_source":"person.legal_full_name","requires_original":false,"position":1},
    {"id":"child_date_of_birth","label":"Child date of birth","type":"date","required":true,"prefill_source":"person.date_of_birth","requires_original":false,"position":2},
    {"id":"child_nationality","label":"Child nationality (ISO)","type":"text","required":true,"prefill_source":"person.nationality","requires_original":false,"position":3},
    {"id":"child_passport_number","label":"Child passport number","type":"text","required":true,"prefill_source":"person.passport_number","requires_original":true,"position":4},
    {"id":"child_passport_expiry","label":"Child passport expiry","type":"date","required":true,"prefill_source":"person.passport_expiry","requires_original":false,"position":5},
    {"id":"relationship_to_employee","label":"Relationship to employee","type":"select","required":true,"prefill_source":"person.relationship","requires_original":false,"position":6,"options":["biological_child","adopted_child","stepchild"]},
    {"id":"sponsor_full_name","label":"Sponsor (employee) full name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":7}
  ]'::jsonb,
  '[
    {"event":"roadmap.profile_completed","conditions":{"destination_country":"NO","has_children":true},"for_persons":["each_child"],"blocked_by_template_code":null,"priority":90}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- RF-1234 · Address registration (Folkeregisteret)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'RF-1234',
  'Flyttemelding (Address registration with Folkeregisteret)',
  'NO',
  'Skatteetaten',
  'Skatteetaten (Norwegian Tax Administration)',
  'registration',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"dnumber_or_pnumber","label":"D-number or Norwegian personal number","type":"text","required":true,"prefill_source":"profile.dnumber","requires_original":false,"position":3},
    {"id":"prior_address","label":"Previous address (origin country)","type":"text","required":true,"prefill_source":"profile.origin_address","requires_original":false,"position":4},
    {"id":"new_address_norway","label":"New address in Norway","type":"text","required":true,"prefill_source":"case.dest_address","requires_original":false,"position":5},
    {"id":"move_in_date","label":"Date of move-in","type":"date","required":true,"prefill_source":"case.actual_move_date","requires_original":false,"position":6},
    {"id":"reason_for_move","label":"Reason for move to Norway","type":"select","required":true,"prefill_source":"case.purpose","requires_original":false,"position":7,"options":["work","intra_company_transfer","family_join","study","other"]}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"NO"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":80}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- GP-7-04 · D-number application
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'GP-7-04',
  'Søknad om D-nummer',
  'NO',
  'Skatteetaten',
  'Skatteetaten (Norwegian Tax Administration)',
  'tax',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"place_of_birth","label":"Place of birth","type":"text","required":true,"prefill_source":"profile.place_of_birth","requires_original":false,"position":3},
    {"id":"nationality","label":"Nationality (ISO)","type":"text","required":true,"prefill_source":"profile.nationality","requires_original":false,"position":4},
    {"id":"passport_number","label":"Passport number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":5},
    {"id":"employer_name","label":"Employer in Norway","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":6},
    {"id":"employer_org_number","label":"Employer org. number","type":"text","required":true,"prefill_source":"contract.employer_org_number","requires_original":false,"position":7},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":8}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"NO"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":85}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- HELFO-1 · Health insurance registration (BLOCKED by GP-7-04)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'HELFO-1',
  'Helsetrygdregistrering (HELFO membership registration)',
  'NO',
  'HELFO',
  'Helseøkonomiforvaltningen (Norwegian Health Economics Administration)',
  'health',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"dnumber_or_pnumber","label":"D-number or Norwegian personal number","type":"text","required":true,"prefill_source":"profile.dnumber","requires_original":false,"position":2},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":3},
    {"id":"address_norway","label":"Address in Norway","type":"text","required":true,"prefill_source":"case.dest_address","requires_original":false,"position":4},
    {"id":"employer_name","label":"Employer in Norway","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":5},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":6},
    {"id":"prior_health_insurance","label":"Prior health insurance country (if any)","type":"text","required":false,"prefill_source":"profile.origin_country","requires_original":false,"position":7}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"NO"},"for_persons":["employee"],"blocked_by_template_code":"GP-7-04","priority":70}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- RF-1209 · Tax card application (BLOCKED by GP-7-04)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'RF-1209',
  'Søknad om skattekort',
  'NO',
  'Skatteetaten',
  'Skatteetaten (Norwegian Tax Administration)',
  'tax',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"dnumber_or_pnumber","label":"D-number or Norwegian personal number","type":"text","required":true,"prefill_source":"profile.dnumber","requires_original":false,"position":2},
    {"id":"employer_name","label":"Employer in Norway","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":3},
    {"id":"employer_org_number","label":"Employer org. number","type":"text","required":true,"prefill_source":"contract.employer_org_number","requires_original":false,"position":4},
    {"id":"employment_start_date","label":"Employment start date","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":5},
    {"id":"salary_amount","label":"Expected gross annual salary (NOK)","type":"number","required":true,"prefill_source":"contract.salary_amount_nok","requires_original":false,"position":6},
    {"id":"tax_residency_country","label":"Country of tax residency (prior year)","type":"text","required":true,"prefill_source":"profile.origin_country","requires_original":false,"position":7}
  ]'::jsonb,
  '[
    {"event":"roadmap.arrival_confirmed","conditions":{"destination_country":"NO"},"for_persons":["employee"],"blocked_by_template_code":"GP-7-04","priority":70}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- NAV-08 · Bank account registration for payroll
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'NAV-08',
  'Bankkontoregistrering for lønnsutbetaling',
  'NO',
  'NAV',
  'Arbeids- og velferdsetaten (Norwegian Labour and Welfare Administration)',
  'banking',
  '1.0.0',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"dnumber_or_pnumber","label":"D-number or Norwegian personal number","type":"text","required":true,"prefill_source":"profile.dnumber","requires_original":false,"position":2},
    {"id":"bank_name","label":"Bank name","type":"text","required":true,"prefill_source":"banking.bank_name","requires_original":false,"position":3},
    {"id":"iban","label":"IBAN","type":"text","required":true,"prefill_source":"banking.iban","requires_original":false,"position":4},
    {"id":"bic_swift","label":"BIC / SWIFT","type":"text","required":true,"prefill_source":"banking.bic","requires_original":false,"position":5},
    {"id":"employer_name","label":"Employer in Norway","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":6}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"NO"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":60}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- ============================================================
-- END OF SEED
-- ============================================================
-- To apply: supabase db push (or via Supabase MCP apply_migration)
-- ============================================================
