-- ============================================================
-- Sprint K: Add JP (Japan) dossier questions + readiness template
-- ============================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'jp.coe_obtained') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'JP', 'immigration', 'jp.coe_obtained',
      'Has the Certificate of Eligibility (COE) been obtained from the Regional Immigration Services Bureau by the employer?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'jp.work_visa_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'JP', 'immigration', 'jp.work_visa_submitted',
      'Has the Japanese work visa application (Engineer/Specialist in Humanities or equivalent) been submitted at the consulate?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'jp.work_visa_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'JP', 'immigration', 'jp.work_visa_granted',
      'Has the Japanese work visa been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'jp.juminhyo_registered') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'JP', 'registration', 'jp.juminhyo_registered',
      'Have you completed resident registration (Juminhyo) at the municipal office within 14 days of establishing residence?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'jp.my_number') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'JP', 'registration', 'jp.my_number',
      'Have you received your My Number (Individual Number) notification card from the municipality?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'jp.health_insurance') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'JP', 'insurance', 'jp.health_insurance',
      'Are you enrolled in Japanese health insurance via your employer (Shakai Hoken) or the National Health Insurance (Kokumin Kenko Hoken)?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'jp.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'JP', 'immigration', 'jp.dependents',
      'Will any dependents accompany you and require Japanese Dependent (Kazoku Taizai) visas?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 70);
  END IF;

  RAISE NOTICE 'JP dossier questions seeded (idempotent).';
END $$;

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'JP';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'JP readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Japan — Work Visa (Certificate of Eligibility / Engineer / Specialist in Humanities)',
    'Working in Japan requires a Certificate of Eligibility (COE) obtained by your employer from the Regional Immigration Services Bureau, followed by a work visa at the Japanese consulate. After arrival, complete resident registration (Juminhyo) at the municipal office within 14 days and receive your My Number card.',
    'The employer files the COE with the Immigration Services Bureau — processing takes 1–3 months. The most common visa categories are Engineer/Specialist in Humanities/International Services and Highly Skilled Professional (HSP points). Juminhyo registration and My Number enrollment are mandatory within 14 days.',
    'COE is valid for 3 months — employee must use it within this window to obtain the visa and enter Japan. The Highly Skilled Professional (HSP) visa offers a points-based accelerated path to permanent residency. Dependent (Kazoku Taizai) visas required for family members. Residence card (Zairyu Card) issued at port of entry for stays over 90 days.',
    '["Certificate of Eligibility (COE) processing takes 1–3 months — initiate the moment the offer is confirmed.",
      "COE is valid for only 3 months from issuance — employee must obtain the visa and enter Japan within this window.",
      "Juminhyo (resident registration) must be completed at the municipal office within 14 days of establishing residence.",
      "My Number (Individual Number) is required for tax filing, payroll withholding, and social insurance enrollment.",
      "Social insurance (Shakai Hoken: health + pension) enrollment is mandatory for employees and deducted from payroll.",
      "Residence card (Zairyu Card) is issued at the airport for stays over 90 days — carry it at all times."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Employment contract signed confirming role and start date', 'employer', 1, NULL,
     'Required for COE application.',
     'Confirm job category aligns with COE visa category (Engineer/Specialist, Highly Skilled, etc.).', 'jp_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Certificate of Eligibility (COE) obtained from Regional Immigration Services Bureau', 'employer', 1, 1,
     'Your employer applies to the Immigration Services Bureau in Japan. Processing: 1–3 months. You must enter Japan within 3 months of COE issuance.',
     'Critical path — file immediately after offer is confirmed. Retain original COE for employee.', 'jp_coe'),
    (gen_random_uuid(), _tid, 3, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for the intended visa period.', NULL, 'jp_passport'),
    (gen_random_uuid(), _tid, 4, 'Work visa application submitted at Japanese consulate', 'employee', 1, 2,
     'Apply at the Japanese consulate in your country of residence with COE, passport, and photos.',
     'Lead time varies by consulate — book immediately after COE receipt.', 'jp_visa_submitted'),
    (gen_random_uuid(), _tid, 5, 'Work visa granted', 'employee', 1, 4,
     'Check visa sticker validity and permitted activities. Enter Japan before COE expiry.',
     'Retain visa copy; confirm entry date.', 'jp_visa_granted'),
    (gen_random_uuid(), _tid, 6, 'Juminhyo (resident registration) at municipal office within 14 days', 'employee', 1, 5,
     'Register at your local city hall (Shiyakusho/Kuyakusho) within 14 days of establishing residence. Bring residence card, passport, and rental contract.',
     'Juminhyo is required for My Number notification and bank accounts.', 'jp_juminhyo'),
    (gen_random_uuid(), _tid, 7, 'My Number (Individual Number) notification received', 'employee', 1, 6,
     'Delivered by post to your registered address after Juminhyo. Required for tax and social insurance.',
     'Obtain My Number from employee for payroll tax withholding and social insurance.', 'jp_my_number'),
    (gen_random_uuid(), _tid, 8, 'Social insurance (Shakai Hoken) enrolled via employer', 'employer', 1, NULL,
     'Your employer enrols you in health insurance (Kenko Hoken) and pension (Kosei Nenkin) from day one.',
     'Mandatory for employees — deducted from payroll; employer contributes equal amount.', 'jp_shakai_hoken'),
    (gen_random_uuid(), _tid, 9, 'Japanese bank account opened', 'employee', 0, NULL,
     'Requires residence card and Juminhyo. Required for salary in JPY.',
     'Required for payroll — arrange within first 2 weeks.', 'jp_bank_account');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Kickoff — COE application',
     'HR applies for the Certificate of Eligibility at the Regional Immigration Services Bureau.',
     'File COE immediately — processing takes 1–3 months. COE is valid for 3 months from issuance.',
     'hr', 'T-16 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'COE issued',
     'COE received. HR sends the original to you for the consulate visa application.',
     'Issue original COE; book consulate appointment immediately — must enter Japan within 3 months.',
     'employer', 'T-8 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Consulate visa application & grant',
     'Apply at Japanese consulate with COE, passport, and photos. Collect visa.',
     'Track visa application; confirm planned entry date.',
     'employee', 'T-4 to 6 weeks'),
    (gen_random_uuid(), _tid, 4, 'move', 'Arrival in Japan',
     'Enter Japan. Residence card (Zairyu Card) issued at port of entry. Carry it at all times.',
     'Log arrival date; set Juminhyo 14-day reminder.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 5, 'post', 'Juminhyo & My Number',
     'Register at city hall within 14 days. Receive My Number notification by post.',
     'Confirm Juminhyo registration; obtain My Number for payroll and social insurance.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 6, 'post', 'Social insurance & settle-in complete',
     'Employer enrolls you in Shakai Hoken (health + pension). Open Japanese bank account.',
     'Confirm Shakai Hoken enrollment; confirm bank account for payroll; schedule 3-month check-in.',
     'hr', 'T+2 to 4 weeks');

  RAISE NOTICE 'JP readiness template inserted with id %', _tid;
END $$;
