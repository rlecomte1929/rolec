-- ============================================================
-- Sprint K: Add NL (Netherlands) dossier questions + readiness template
-- ============================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'nl.kennismigrant_confirmed') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NL', 'immigration', 'nl.kennismigrant_confirmed',
      'Has the Highly Skilled Migrant (Kennismigrant) permit route been confirmed with the IND by the recognised employer?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'nl.ind_application_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NL', 'immigration', 'nl.ind_application_submitted',
      'Has the IND (Immigratie en Naturalisatiedienst) permit application been submitted by the employer?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'nl.residence_permit_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NL', 'immigration', 'nl.residence_permit_granted',
      'Has the Dutch residence permit (verblijfsvergunning) been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'nl.bsn_obtained') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NL', 'registration', 'nl.bsn_obtained',
      'Have you obtained a BSN (Burgerservicenummer — Dutch citizen service number) at the municipality?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'nl.health_insurance') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NL', 'insurance', 'nl.health_insurance',
      'Is mandatory Dutch health insurance (basisverzekering) in place? (Required within 4 months of registering as resident)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'nl.digid_applied') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NL', 'registration', 'nl.digid_applied',
      'Have you applied for a DigiD (Dutch digital identity) for access to online government services?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'nl.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NL', 'immigration', 'nl.dependents',
      'Will any dependents accompany you and require Dutch family reunification permits?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 70);
  END IF;

  RAISE NOTICE 'NL dossier questions seeded (idempotent).';
END $$;

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'NL';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'NL readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Netherlands — Highly Skilled Migrant Permit (Kennismigrant) / IND',
    'The Highly Skilled Migrant (Kennismigrant) permit is the main route for non-EU/EEA skilled workers in the Netherlands. Your employer — a recognised IND sponsor — files the application; the residence permit is typically issued within 2 weeks. EU/EEA nationals have free movement rights. All residents need a BSN and mandatory Dutch health insurance.',
    'The employer must be a recognised IND sponsor (register separately if not). The Kennismigrant salary threshold must be met (check current IND rates). The 30% ruling may provide a significant tax advantage for incoming skilled workers. BSN is mandatory before payroll.',
    'IND processing for Kennismigrant: typically 2 weeks once application is complete. 30% ruling application should be filed within 4 months of first employment in NL. EU Blue Card is an alternative for high-salary roles. Spouse of Kennismigrant holder receives an unrestricted work permit automatically. Dutch health insurance (basisverzekering) must be arranged within 4 months of registration.',
    '["The employer must be a recognised IND sponsor before the Kennismigrant permit can be filed.",
      "Salary threshold for the Kennismigrant permit must be met — verify current IND thresholds (updated annually).",
      "BSN (Burgerservicenummer) must be obtained before payroll can be processed legally.",
      "Mandatory Dutch health insurance (basisverzekering) must be arranged within 4 months of registering as a resident.",
      "The 30% tax ruling provides significant tax relief for incoming workers — apply within 4 months of first employment.",
      "DigiD (Dutch digital identity) is required for online government services — apply as early as possible."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Employer confirmed as recognised IND sponsor', 'employer', 1, NULL,
     'Your employer must be registered as a recognised sponsor with the IND before filing your permit.',
     'Check IND sponsor status at ind.nl. If not yet registered, allow 4–6 weeks to become a recognised sponsor.', 'nl_ind_sponsor'),
    (gen_random_uuid(), _tid, 2, 'Signed employment contract meeting Kennismigrant salary threshold', 'employer', 1, 1,
     'Salary must meet the IND annual threshold (check current rates at ind.nl).',
     'Verify salary threshold meets current year requirement; threshold is updated annually.', 'nl_offer_letter'),
    (gen_random_uuid(), _tid, 3, 'Kennismigrant permit application submitted to IND', 'employer', 1, 2,
     'Employer files online via the IND portal. Processing: typically 2 weeks for recognised sponsors.',
     'File as soon as contract is signed. Track IND reference number.', 'nl_ind_application'),
    (gen_random_uuid(), _tid, 4, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for the permit duration.', NULL, 'nl_passport'),
    (gen_random_uuid(), _tid, 5, 'Residence permit (verblijfsvergunning) granted', 'employee', 1, 3,
     'Permit sticker issued at the Dutch mission in your home country (non-EEA nationals) or at IND in NL.',
     'Confirm collection method — IND will advise.', 'nl_residence_permit'),
    (gen_random_uuid(), _tid, 6, 'BSN (Burgerservicenummer) obtained at municipality', 'employee', 1, 5,
     'Register at the local municipality (gemeente) with passport, residence permit, and rental contract. BSN is issued immediately or within a few days.',
     'BSN is required before payroll can run — chase immediately after arrival.', 'nl_bsn'),
    (gen_random_uuid(), _tid, 7, 'Mandatory Dutch health insurance (basisverzekering) enrolled', 'employee', 1, NULL,
     'Arrange through a Dutch insurer (Zorgverzekeraar) within 4 months of registering as a resident.',
     'Confirm enrollment; check if employer provides collective supplemental insurance.', 'nl_health_insurance'),
    (gen_random_uuid(), _tid, 8, 'DigiD applied for', 'employee', 0, 6,
     'Apply at digid.nl — required for online government services.',
     'Strongly recommended for the 30% ruling application and other government interactions.', 'nl_digid'),
    (gen_random_uuid(), _tid, 9, '30% ruling application submitted (if eligible)', 'employer', 0, 6,
     'If eligible, the 30% ruling allows 30% of your salary to be paid tax-free. Apply within 4 months of first employment.',
     '30% ruling can be significant — file jointly with employee within 4 months of start date.', 'nl_30pct_ruling');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'IND sponsor confirmation & application',
     'Employer confirms IND sponsor status and files Kennismigrant permit application.',
     'Verify IND sponsor status; file Kennismigrant application immediately after contract is signed. Processing: ~2 weeks.',
     'hr', 'T-6 weeks'),
    (gen_random_uuid(), _tid, 2, 'immigration', 'Residence permit granted',
     'Permit granted. Collect from Dutch mission (non-EEA) or IND in NL.',
     'Confirm collection; brief employee on BSN and health insurance steps.',
     'hr', 'T-4 weeks'),
    (gen_random_uuid(), _tid, 3, 'move', 'Arrival & BSN registration',
     'Arrive in the Netherlands. Register at the municipality (gemeente) to obtain your BSN.',
     'Log arrival; initiate BSN onboarding and health insurance enrollment.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 4, 'post', 'BSN, health insurance & DigiD',
     'Obtain BSN at gemeente. Arrange basisverzekering health insurance within 4 months. Apply for DigiD.',
     'Confirm BSN on file before first payroll; file 30% ruling within 4 months of start.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 5, 'post', '30% ruling & settle-in complete',
     '30% ruling filed (if eligible). Open Dutch bank account. Arrange schooling for children if applicable.',
     'Confirm 30% ruling filed; schedule 3-month and annual permit renewal check-ins.',
     'hr', 'T+2 to 4 weeks');

  RAISE NOTICE 'NL readiness template inserted with id %', _tid;
END $$;
