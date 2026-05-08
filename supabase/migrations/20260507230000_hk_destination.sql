-- ============================================================
-- Sprint K: Add HK (Hong Kong) dossier questions + readiness template
-- ============================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'hk.employment_visa_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'HK', 'immigration', 'hk.employment_visa_submitted',
      'Has the employment visa application been submitted to the Hong Kong Immigration Department?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'hk.employment_visa_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'HK', 'immigration', 'hk.employment_visa_granted',
      'Has the Hong Kong employment visa been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'hk.hkid_obtained') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'HK', 'registration', 'hk.hkid_obtained',
      'Have you obtained your Hong Kong Identity Card (HKID) at an Immigration Services Centre within 30 days of arrival?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'hk.mpf_enrolled') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'HK', 'registration', 'hk.mpf_enrolled',
      'Has your employer enrolled you in the Mandatory Provident Fund (MPF) scheme within 60 days?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'hk.ird_tax') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'HK', 'registration', 'hk.ird_tax',
      'Have you noted your obligations with the Inland Revenue Department (IRD) for salaries tax?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'hk.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'HK', 'immigration', 'hk.dependents',
      'Will any dependents accompany you and require Hong Kong Dependant Visas?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 60);
  END IF;

  RAISE NOTICE 'HK dossier questions seeded (idempotent).';
END $$;

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'HK';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'HK readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Hong Kong — Employment Visa (General Employment Policy)',
    'Foreign nationals require an employment visa from the Hong Kong Immigration Department. The employer sponsors the application. After arrival, obtain your HKID within 30 days and ensure your employer enrolls you in the Mandatory Provident Fund (MPF) within 60 days.',
    'Employment visa applications are employer-sponsored and processed by the HKID Department. Processing: 4–6 weeks. HKID must be obtained within 30 days of arrival. MPF enrollment is mandatory within 60 days of employment commencement.',
    'GEP requires proof the position cannot be filled locally. Salary should be commensurate with the local market rate. The Quality Migrant Admission Scheme (QMAS) is an alternative for high-talent individuals. Dependent visas available for spouses and unmarried children under 18.',
    '["HKID must be obtained within 30 days of first landing — fines apply for non-compliance.",
      "MPF enrollment is mandatory within 60 days of employment commencement.",
      "Employment visa is employer-specific — a new visa is required if the employee changes employer.",
      "No general income tax filing for most employees, but a tax return may be issued by IRD — respond within the deadline.",
      "Dependent visa holders may not work without a separate work visa."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Employment offer letter confirming role, salary, and duration', 'employer', 1, NULL,
     'Required for visa application.',
     'Demonstrate that the position cannot be filled locally.', 'hk_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for at least 1 month beyond intended stay.', NULL, 'hk_passport'),
    (gen_random_uuid(), _tid, 3, 'Employment visa application submitted to Hong Kong Immigration Department', 'employer', 1, 1,
     'Employer-sponsored; application includes proof of qualifications and employment contract.',
     'Processing typically 4–6 weeks. Apply online at immd.gov.hk.', 'hk_visa_submitted'),
    (gen_random_uuid(), _tid, 4, 'Employment visa granted', 'employee', 1, 3,
     'Check visa approval letter for conditions and entry instructions.',
     'Retain copy; confirm start date.', 'hk_visa_granted'),
    (gen_random_uuid(), _tid, 5, 'HKID (Hong Kong Identity Card) obtained within 30 days of arrival', 'employee', 1, 4,
     'Visit an Immigration Services Centre (ISC) within 30 days of arrival with your passport and visa approval letter.',
     'Track HKID registration date — mandatory legal requirement.', 'hk_hkid'),
    (gen_random_uuid(), _tid, 6, 'MPF (Mandatory Provident Fund) enrollment within 60 days', 'employer', 1, NULL,
     'Your employer registers you with an MPF scheme. Both employer and employee contribute 5% of relevant income.',
     'Enroll within 60 days of employment commencement. Choose an MPF trustee.', 'hk_mpf'),
    (gen_random_uuid(), _tid, 7, 'Hong Kong bank account opened', 'employee', 0, NULL,
     'Requires HKID, employment visa, and employer letter. Required for HKD salary payment.',
     'Required for payroll — arrange before first pay date.', 'hk_bank_account'),
    (gen_random_uuid(), _tid, 8, 'Tax obligations with IRD noted', 'employee', 0, NULL,
     'IRD may issue a salaries tax return — respond within 1 month if received.',
     'Inform employee of IRD obligations and tax equalization policy if applicable.', 'hk_tax');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Visa application submitted',
     'Employer submits employment visa application to Immigration Department.',
     'Prepare full application pack including employment contract, qualifications, and employer letter. Processing: 4–6 weeks.',
     'hr', 'T-8 weeks'),
    (gen_random_uuid(), _tid, 2, 'immigration', 'Visa granted',
     'Visa approval letter received. Plan your travel and entry date.',
     'Retain copy; confirm start date; brief employee on HKID 30-day rule.',
     'hr', 'T-4 weeks'),
    (gen_random_uuid(), _tid, 3, 'move', 'Arrival & HKID registration',
     'Enter Hong Kong. Register for HKID at an Immigration Services Centre within 30 days.',
     'Log arrival date; set HKID 30-day reminder; initiate MPF enrollment.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 4, 'post', 'MPF & banking',
     'Employer enrolls you in MPF. Open Hong Kong bank account for salary payments.',
     'Complete MPF enrollment within 60 days; confirm bank account details for payroll.',
     'employer', 'T+1 to 4 weeks'),
    (gen_random_uuid(), _tid, 5, 'post', 'Settle-in complete',
     'Confirm HKID received. Open bank account. Arrange schooling for children if applicable.',
     'Confirm all registrations; schedule annual visa renewal check-in.',
     'hr', 'T+4 to 6 weeks');

  RAISE NOTICE 'HK readiness template inserted with id %', _tid;
END $$;
