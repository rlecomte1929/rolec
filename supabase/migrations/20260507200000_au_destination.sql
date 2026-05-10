-- ============================================================
-- Sprint K: Add AU (Australia) dossier questions + readiness template
-- ============================================================

-- ── Dossier questions ─────────────────────────────────────────────────────────

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.visa_type_confirmed') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'immigration', 'au.visa_type_confirmed',
      'Has the visa type been confirmed by your employer? (Temporary Skill Shortage subclass 482, or Employer Nomination subclass 186)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.labour_market_testing') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'immigration', 'au.labour_market_testing',
      'Has Labour Market Testing (LMT) been completed and documented by the employer?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.skills_assessment') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'immigration', 'au.skills_assessment',
      'Has the skills assessment been submitted to the relevant Australian assessing authority (if required for your occupation)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.visa_lodged') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'immigration', 'au.visa_lodged',
      'Has the visa application been lodged with the Australian Department of Home Affairs?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.tfn_applied') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'registration', 'au.tfn_applied',
      'Have you applied for a Tax File Number (TFN) with the Australian Taxation Office (ATO)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.medicare_health') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'insurance', 'au.medicare_health',
      'Have you enrolled in Medicare (if eligible) or arranged private overseas health insurance?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.superannuation') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'registration', 'au.superannuation',
      'Has your employer nominated or confirmed a superannuation fund for compulsory contributions?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 70);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'au.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'AU', 'immigration', 'au.dependents',
      'Will any dependents accompany you and require Australian secondary applicant visas?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 80);
  END IF;

  RAISE NOTICE 'AU dossier questions seeded (idempotent).';
END $$;

-- ── Readiness template ────────────────────────────────────────────────────────

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'AU';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'AU readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Australia — TSS Subclass 482 / Employer Nomination Subclass 186',
    'Your employer nominates you for either a Temporary Skill Shortage (subclass 482) visa or the permanent Employer Nomination Scheme (subclass 186). Labour Market Testing and, for some occupations, a skills assessment are required before lodgement. After arrival, obtain a Tax File Number (TFN) and enrol in superannuation.',
    'Labour Market Testing must be documented before the nomination is lodged. Confirm occupation eligibility on the MLTSSL/STSOL lists. Subclass 186 (ENS) offers a permanent pathway. Ensure TFN and superannuation are set up before first payroll.',
    'Subclass 482 (TSS) requires Labour Market Testing unless covered by international agreement. Occupation must be on the relevant skilled occupation list. Superannuation is compulsory (currently 11%). Medical examination may be required depending on nationality/occupation.',
    '["Labour Market Testing (LMT) must be conducted and documented within 12 months before lodging the nomination — advertising requirements apply.",
      "Skills assessments may be required for some occupations — confirm with the relevant assessing authority before starting the process.",
      "Subclass 482 is a temporary visa; align renewal dates with contract length and plan permanent pathway (subclass 186) early.",
      "TFN must be obtained before payroll — without it, the employer must withhold tax at the highest marginal rate.",
      "Superannuation contributions are compulsory — employer must enrol the employee within 28 days of eligibility.",
      "Visa holders on subclass 482 may only work for the sponsoring employer — any role change requires a new nomination."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Signed employment contract confirming role, salary, and work location', 'employer', 1, NULL,
     'Required for nomination lodgement.',
     'Confirm role is on eligible occupation list (MLTSSL/STSOL/PMSOL).', 'au_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Labour Market Testing (LMT) completed and documented', 'employer', 1, 1,
     'Your employer must advertise the role and show no suitable Australian worker was available.',
     'LMT advertising must be within 12 months prior to nomination lodgement — keep records of all ads and applicants.', 'au_lmt'),
    (gen_random_uuid(), _tid, 3, 'Skills assessment submitted (if required for occupation)', 'employee', 1, NULL,
     'Contact the relevant assessing authority for your occupation. Lead time: 4–12 weeks.',
     'Confirm if skills assessment is required for the specific ANZSCO occupation code.', 'au_skills_assessment'),
    (gen_random_uuid(), _tid, 4, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for the intended visa period.', NULL, 'au_passport'),
    (gen_random_uuid(), _tid, 5, 'Visa nomination and application lodged with Home Affairs', 'employer', 1, 2,
     'Employer lodges the nomination; you then lodge the visa application online.',
     'Track nomination and visa application reference numbers. Processing: 2–8 months depending on stream.', 'au_visa_lodged'),
    (gen_random_uuid(), _tid, 6, 'Visa granted', 'employee', 1, 5,
     'Check visa grant notice for conditions, validity dates, and any travel restrictions.',
     'Retain grant notice; confirm planned entry date and start date.', 'au_visa_granted'),
    (gen_random_uuid(), _tid, 7, 'Tax File Number (TFN) applied for with ATO', 'employee', 1, NULL,
     'Apply at ato.gov.au or at a Medicare office. Required for payroll and banking.',
     'Withhold maximum tax rate until TFN is provided — chase promptly after arrival.', 'au_tfn'),
    (gen_random_uuid(), _tid, 8, 'Superannuation fund nominated', 'employer', 1, NULL,
     'You may choose your own fund or use the employer''s default. Complete the Standard Choice Form.',
     'Enrol within 28 days of becoming eligible; SG contributions currently 11%.', 'au_super'),
    (gen_random_uuid(), _tid, 9, 'Medicare or private health insurance arranged', 'employee', 0, NULL,
     'Medicare eligibility depends on your nationality and visa type. If not eligible, arrange OVHC (Overseas Visitor Health Cover).',
     'Confirm Medicare eligibility; some nationalities and visa holders require private OVHC cover.', 'au_health');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Kickoff — LMT and nomination preparation',
     'HR begins Labour Market Testing, confirms your occupation is eligible, and prepares the nomination.',
     'Conduct LMT advertising; document all applicants; confirm occupation list eligibility before lodging nomination.',
     'hr', 'T-20 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'Nomination and visa application lodged',
     'Nomination lodged by HR; you receive an invitation to complete your visa application online.',
     'Track nomination reference; guide employee through online visa application.',
     'employer', 'T-16 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Visa granted',
     'Check grant notice for conditions and validity. Plan your travel date accordingly.',
     'Record grant date and visa expiry; align start date.',
     'hr', 'T-4 to 8 weeks'),
    (gen_random_uuid(), _tid, 4, 'move', 'Arrival in Australia',
     'Enter Australia. Your visa is electronically linked to your passport — no label required.',
     'Log arrival date; initiate TFN and superannuation onboarding.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 5, 'post', 'TFN, superannuation & healthcare',
     'Apply for TFN online. Complete the superannuation choice form. Enrol in Medicare or arrange private health cover.',
     'Confirm TFN and super fund on file before first payroll run.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 6, 'post', 'Settle-in complete',
     'Open Australian bank account. Register with local GP. Organise schooling for children if applicable.',
     'Schedule 3-month and 12-month check-ins; set visa renewal reminder.',
     'hr', 'T+4 weeks');

  RAISE NOTICE 'AU readiness template inserted with id %', _tid;
END $$;
