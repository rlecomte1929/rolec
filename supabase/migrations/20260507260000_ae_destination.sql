-- ============================================================
-- Sprint K: Add AE (UAE) dossier questions + readiness template
-- ============================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ae.entry_permit_obtained') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AE', 'immigration', 'ae.entry_permit_obtained',
      'Has the Employment Entry Permit been obtained from MOHRE (Ministry of Human Resources and Emiratisation)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ae.medical_fitness') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AE', 'immigration', 'ae.medical_fitness',
      'Has the mandatory medical fitness test (including blood test and chest X-ray) been completed in the UAE?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ae.residence_visa_stamped') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AE', 'immigration', 'ae.residence_visa_stamped',
      'Has the UAE residence visa been stamped in the passport by the General Directorate of Residency and Foreigners Affairs (GDRFA)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ae.emirates_id') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AE', 'registration', 'ae.emirates_id',
      'Has the Emirates ID application been submitted to the ICP (Federal Authority for Identity, Citizenship, Customs and Port Security)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ae.work_permit_issued') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AE', 'registration', 'ae.work_permit_issued',
      'Has the MOHRE work permit / labour card been issued?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ae.health_insurance') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AE', 'insurance', 'ae.health_insurance',
      'Is UAE mandatory health insurance in place? (Required by law; employer must provide for employees in Dubai and Abu Dhabi)',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ae.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AE', 'immigration', 'ae.dependents',
      'Will any dependents accompany you and require UAE residence visas as your dependants?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 70);
  END IF;

  RAISE NOTICE 'AE dossier questions seeded (idempotent).';
END $$;

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'AE';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'AE readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'UAE — Employment Entry Permit / Residence Visa / Emirates ID',
    'Working in the UAE requires an Employment Entry Permit from MOHRE, followed by a mandatory medical fitness test, a residence visa stamped by GDRFA, and an Emirates ID from the ICP. The employer initiates the entire process. The typical timeline from entry permit to active residence visa is 4–6 weeks.',
    'The employer initiates the process by obtaining the Employment Entry Permit. The employee then enters the UAE, passes the medical fitness test, and the residence visa is stamped. Emirates ID is applied for alongside the residence visa application. MOHRE work permit (labour card) must be issued.',
    'UAE has a 2-year renewable residence visa for most employees (3 or 5 years for highly skilled under Golden Visa). Health insurance is mandatory by law and is the employer''s responsibility in Dubai and Abu Dhabi. No income tax in UAE. End-of-Service Gratuity (EOSG) must be accrued for all employees. DIFC and ADGM operate under separate common law jurisdictions.',
    '["The Employment Entry Permit must be obtained before the employee enters the UAE.",
      "Mandatory medical fitness test (HIV, tuberculosis, hepatitis tests) must be passed — some conditions result in visa refusal.",
      "Emirates ID must be applied for alongside the residence visa — it is the primary identification document in UAE.",
      "UAE mandatory health insurance is the employer''s legal responsibility in Dubai and Abu Dhabi.",
      "MOHRE work permit must be issued and aligned with the residence visa.",
      "Dependents require separate sponsored residence visas — income threshold requirements apply."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Employment offer / contract signed', 'employer', 1, NULL,
     'Required for MOHRE entry permit application.',
     'Contract must be attested and meet MOHRE standard.', 'ae_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Employment Entry Permit (EEP) obtained from MOHRE', 'employer', 1, 1,
     'Your employer obtains the EEP online. You cannot legally work until this is obtained.',
     'Apply via MOHRE portal. EEP is valid for 60 days from issuance. Critical path item.', 'ae_entry_permit'),
    (gen_random_uuid(), _tid, 3, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for at least 6 months. Passport is held during residence visa stamping.', NULL, 'ae_passport'),
    (gen_random_uuid(), _tid, 4, 'Entry into UAE on employment entry permit', 'employee', 1, 2,
     'Enter UAE using the entry permit (not a tourist visa). Arrange arrival with HR.',
     'Confirm employee enters on the correct permit; tourist visa entry is invalid for employment.', 'ae_entry'),
    (gen_random_uuid(), _tid, 5, 'Medical fitness test completed', 'employee', 1, 4,
     'Blood test and chest X-ray at an accredited UAE medical facility. Results usually within 1–2 days.',
     'Failing the fitness test will void the visa process.', 'ae_medical'),
    (gen_random_uuid(), _tid, 6, 'UAE residence visa stamped in passport', 'employer', 1, 5,
     'Employer submits residence visa application to GDRFA. Passport held for 3–7 days for stamping.',
     'Apply via GDRFA immediately after medical clearance. Issue Emirates ID application in parallel.', 'ae_residence_visa'),
    (gen_random_uuid(), _tid, 7, 'Emirates ID applied for and received', 'employee', 1, 6,
     'Apply at an ICP service centre or via the UAEPASS app. Emirates ID issued within 5–10 working days.',
     'Emirates ID is the primary document for all UAE services and contracts.', 'ae_emirates_id'),
    (gen_random_uuid(), _tid, 8, 'MOHRE work permit (labour card) issued', 'employer', 1, 6,
     'Issued by MOHRE alongside the residence visa. Required for lawful employment.',
     'File MOHRE work permit application aligned with residence visa timeline.', 'ae_work_permit'),
    (gen_random_uuid(), _tid, 9, 'Mandatory health insurance arranged', 'employer', 0, NULL,
     'UAE law requires your employer to provide health insurance in Dubai and Abu Dhabi from day one.',
     'Mandatory for employers in Dubai (all employees) and Abu Dhabi (all residents). Arrange before first working day.', 'ae_health_insurance');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Kickoff — Employment Entry Permit',
     'HR obtains the Employment Entry Permit from MOHRE. You must enter UAE using this permit.',
     'Apply via MOHRE portal immediately after contract is signed. EEP valid 60 days — do not delay entry.',
     'hr', 'T-4 weeks'),
    (gen_random_uuid(), _tid, 2, 'move', 'Arrival & medical fitness test',
     'Enter UAE on entry permit. Complete mandatory medical fitness test at an accredited facility.',
     'Log arrival; book medical test on arrival day if possible; retain medical clearance certificate.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Residence visa & Emirates ID',
     'Employer submits residence visa application. Passport held 3–7 days. Emirates ID application submitted in parallel.',
     'Apply to GDRFA for residence visa and ICP for Emirates ID simultaneously.',
     'employer', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 4, 'immigration', 'Residence visa stamped & work permit issued',
     'Collect stamped passport. Receive Emirates ID (5–10 working days after application).',
     'Confirm MOHRE work permit issued alongside visa. Update HR system with visa/permit expiry dates.',
     'hr', 'T+2 to 3 weeks'),
    (gen_random_uuid(), _tid, 5, 'post', 'Settle-in & banking',
     'Open UAE bank account with Emirates ID and residence visa. Arrange accommodation. Enrol dependents if applicable.',
     'Confirm health insurance active; schedule visa renewal reminder (2 years); confirm end-of-service gratuity accrual starts.',
     'employee', 'T+3 to 4 weeks');

  RAISE NOTICE 'AE readiness template inserted with id %', _tid;
END $$;
