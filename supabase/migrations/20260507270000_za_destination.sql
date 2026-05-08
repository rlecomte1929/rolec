-- ============================================================
-- Sprint K: Add ZA (South Africa) dossier questions + readiness template
-- ============================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'za.visa_type_confirmed') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ZA', 'immigration', 'za.visa_type_confirmed',
      'Has the visa type been confirmed? (Critical Skills Work Visa, General Work Visa, or Intra-Company Transfer Work Visa)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'za.saqa_evaluation') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ZA', 'immigration', 'za.saqa_evaluation',
      'Has the SAQA (South African Qualifications Authority) foreign qualification evaluation been submitted?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'za.work_visa_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ZA', 'immigration', 'za.work_visa_submitted',
      'Has the South African work visa application been submitted at the nearest VFS Global / SA mission?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'za.work_visa_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ZA', 'immigration', 'za.work_visa_granted',
      'Has the South African work visa been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'za.sars_tax_number') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ZA', 'registration', 'za.sars_tax_number',
      'Have you registered with SARS (South African Revenue Service) for a South African tax number?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'za.health_insurance') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ZA', 'insurance', 'za.health_insurance',
      'Do you have private health insurance (medical aid scheme) in South Africa? (Public healthcare has long wait times — private cover is strongly recommended)',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'za.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ZA', 'immigration', 'za.dependents',
      'Will any dependents accompany you and require South African relative''s visas?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 70);
  END IF;

  RAISE NOTICE 'ZA dossier questions seeded (idempotent).';
END $$;

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'ZA';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'ZA readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'South Africa — Critical Skills Work Visa / General Work Visa',
    'Non-citizens working in South Africa require a work visa. The Critical Skills Work Visa is available for occupations on the DoL Critical Skills List. The General Work Visa requires a Labour Market Test confirming no suitable South African candidate was available. Foreign qualifications must be evaluated by SAQA. After arrival, register with SARS for a tax number.',
    'Visa route depends on whether the occupation appears on the DTIC/DoL Critical Skills List. The General Work Visa requires the employer to conduct and document a Labour Market Test. Intracompany Transfer (ICT) visas are available for multinationals. Processing typically takes 4–8 weeks at a VFS centre.',
    'Critical Skills Work Visa: valid for 3–5 years, renewable; no formal job offer needed but proof of qualification and critical skills required. General Work Visa: employer must prove no suitable SA/permanent resident candidate available. ICT: employee must have worked for the same employer for 6 months and have skills not available in SA. Biometric data collected at a VFS Global centre.',
    '["SAQA foreign qualification evaluation takes 4–6 weeks — initiate early as it is required for most visa categories.",
      "Police clearance certificate from every country of residence for 12+ months in the past 5 years is required.",
      "General Work Visa requires Labour Market Testing proof — employer must advertise and document search for a suitable SA candidate.",
      "Visa processing at VFS can take 4–8 weeks — submit well in advance of the planned start date.",
      "SARS registration is required for tax compliance — must be completed before employment begins.",
      "Private health insurance (medical aid) is strongly recommended — public hospitals have very long waiting times."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Visa type determined (Critical Skills, General Work, or ICT)', 'employer', 1, NULL,
     'HR will advise on which visa category applies to your occupation and circumstances.',
     'Check DTIC/DoL Critical Skills List. If not on the list, proceed with General Work Visa and arrange Labour Market Test.', 'za_visa_type'),
    (gen_random_uuid(), _tid, 2, 'SAQA foreign qualification evaluation submitted', 'employee', 1, 1,
     'Submit your foreign qualification documents to SAQA (saqa.org.za). Processing: 4–6 weeks.',
     'SAQA evaluation is required for most work visa categories. Initiate as early as possible.', 'za_saqa'),
    (gen_random_uuid(), _tid, 3, 'Police clearance certificate(s) obtained', 'employee', 1, NULL,
     'Required from every country you have lived in for 12+ months in the past 5 years. Allow 4–8 weeks.',
     'International police clearances take time — initiate in parallel with SAQA evaluation.', 'za_police_clearance'),
    (gen_random_uuid(), _tid, 4, 'Labour Market Test completed (General Work Visa only)', 'employer', 0, 1,
     'Your employer must advertise the role and show no suitable South African candidate was found.',
     'Document all advertising and applicant responses. Obtain a confirmation letter from the Dept of Employment and Labour.', 'za_lmt'),
    (gen_random_uuid(), _tid, 5, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for at least 30 days beyond the intended visa validity.', NULL, 'za_passport'),
    (gen_random_uuid(), _tid, 6, 'Work visa application submitted at VFS Global / SA mission', 'employee', 1, 2,
     'Submit full application pack at VFS Global: passport, SAQA evaluation, police clearance, medical certificate, photos, and employment contract.',
     'Track VFS reference; processing 4–8 weeks. Prepare for supplemental document requests.', 'za_visa_submitted'),
    (gen_random_uuid(), _tid, 7, 'Work visa granted', 'employee', 1, 6,
     'Check visa validity dates and conditions.',
     'Retain copy; align start date; set renewal reminder.', 'za_visa_granted'),
    (gen_random_uuid(), _tid, 8, 'SARS tax registration completed', 'employee', 1, 7,
     'Register with SARS at a SARS branch or via eFiling. Obtain a South African tax number.',
     'Tax number required before payroll; employer must register employee for PAYE.', 'za_sars'),
    (gen_random_uuid(), _tid, 9, 'Private health insurance (medical aid) arranged', 'employee', 0, NULL,
     'Public healthcare has long wait times — private medical aid scheme is strongly recommended.',
     'Confirm employer medical aid scheme inclusion; arrange from first working day.', 'za_health_insurance');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'SAQA evaluation, police clearance & LMT',
     'Submit SAQA qualification evaluation. Obtain police clearances. HR initiates Labour Market Test if required.',
     'Run SAQA, police clearance, and LMT in parallel — allow 4–8 weeks.',
     'employer', 'T-16 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'Full document pack compiled',
     'All documents gathered: SAQA evaluation, police clearances, medical certificate, passport, photos, employment contract.',
     'Review document pack for completeness before VFS submission.',
     'employee', 'T-8 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Work visa application submitted at VFS',
     'Attend VFS Global appointment with full document pack. Biometric data collected.',
     'Track VFS reference; processing 4–8 weeks; prepare for supplemental requests.',
     'employee', 'T-6 weeks'),
    (gen_random_uuid(), _tid, 4, 'immigration', 'Work visa granted',
     'Check visa conditions. Plan travel date.',
     'Retain visa copy; confirm start date; set renewal reminder.',
     'hr', 'T-2 to 4 weeks'),
    (gen_random_uuid(), _tid, 5, 'move', 'Arrival in South Africa',
     'Enter South Africa. Retain your passport entry stamp.',
     'Log arrival; initiate SARS registration and banking onboarding.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 6, 'post', 'SARS registration & banking',
     'Register with SARS for a tax number (eFiling or SARS branch). Open a South African bank account.',
     'Confirm SARS number before first payroll run; ensure PAYE registration.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 7, 'post', 'Settle-in complete',
     'Arrange private medical aid. Enrol children in school if applicable.',
     'Confirm medical aid active; schedule 3-month check-in; set visa renewal reminder.',
     'hr', 'T+2 to 4 weeks');

  RAISE NOTICE 'ZA readiness template inserted with id %', _tid;
END $$;
