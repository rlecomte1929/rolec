-- ============================================================
-- Sprint K: Add CA (Canada) dossier questions + readiness template
-- ============================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ca.permit_route_confirmed') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CA', 'immigration', 'ca.permit_route_confirmed',
      'Has the work permit route been confirmed? (LMIA-required, LMIA-exempt via CUSMA/USMCA, Intracompany Transfer, or Express Entry)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ca.lmia_obtained') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CA', 'immigration', 'ca.lmia_obtained',
      'Has the employer obtained a positive Labour Market Impact Assessment (LMIA) from ESDC (if required for your work permit route)?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ca.work_permit_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CA', 'immigration', 'ca.work_permit_submitted',
      'Has the Canadian work permit application been submitted online or at a port of entry?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ca.work_permit_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CA', 'immigration', 'ca.work_permit_granted',
      'Has the Canadian work permit been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ca.sin_obtained') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CA', 'registration', 'ca.sin_obtained',
      'Have you obtained a Social Insurance Number (SIN) from Service Canada?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ca.provincial_health') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CA', 'insurance', 'ca.provincial_health',
      'Have you enrolled in the provincial health insurance plan? (Note: most provinces have a 3-month waiting period — interim private insurance is recommended)',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ca.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CA', 'immigration', 'ca.dependents',
      'Will any dependents accompany you and require open or restricted Canadian work/study permits?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 70);
  END IF;

  RAISE NOTICE 'CA dossier questions seeded (idempotent).';
END $$;

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'CA';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'CA readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Canada — Employer-Specific Work Permit (LMIA / LMIA-Exempt)',
    'Most foreign workers in Canada require an employer-specific work permit. The route is either LMIA-based (employer obtains a positive Labour Market Impact Assessment from ESDC) or LMIA-exempt (e.g. CUSMA/USMCA, Intracompany Transfer, or international agreements). After arrival, obtain a Social Insurance Number (SIN) and enrol in provincial health insurance.',
    'Confirm the correct route: LMIA-based vs LMIA-exempt (CUSMA, ICT, C-11, etc.). LMIA takes 2–5 months — start immediately. LMIA-exempt routes are faster but require the correct legal basis. SIN must be obtained before payroll; provincial health insurance has a 3-month waiting period in most provinces.',
    'LMIA-based: employer must advertise and show no qualified Canadian was available. LMIA-exempt: document the legal basis carefully (e.g. CUSMA profession list, ICT relationship). Intracompany Transfers (C-12) require 1 year with the same company abroad. Express Entry PR pathway available in parallel.',
    '["LMIA processing can take 2–5 months — initiate immediately if LMIA route is required.",
      "Most provinces have a 3-month waiting period for provincial health insurance — arrange private health coverage from day one.",
      "The work permit is employer-specific — a new work permit is required for role changes.",
      "SIN must be obtained from Service Canada before payroll can run legally.",
      "Open work permits are available for spouses of skilled workers — apply in parallel for dependents."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Work permit route confirmed (LMIA-based or LMIA-exempt)', 'employer', 1, NULL,
     'HR will confirm whether an LMIA is required based on your role and nationality.',
     'Review CUSMA profession list, C-12 ICT eligibility, or other LMIA-exempt codes before pursuing LMIA route.', 'ca_route_confirmed'),
    (gen_random_uuid(), _tid, 2, 'LMIA obtained from ESDC (if required)', 'employer', 0, 1,
     'Your employer applies to ESDC. Allow 2–5 months. You will be notified of the outcome.',
     'Advertise per ESDC requirements; retain all records. Process takes 2–5 months in high-wage stream.', 'ca_lmia'),
    (gen_random_uuid(), _tid, 3, 'Signed employment contract and offer letter', 'employer', 1, NULL,
     'Required for work permit application.',
     'Ensure offer specifies NOC code, wage, hours, and duration.', 'ca_offer_letter'),
    (gen_random_uuid(), _tid, 4, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for the intended work permit period.', NULL, 'ca_passport'),
    (gen_random_uuid(), _tid, 5, 'Work permit application submitted online or at port of entry', 'employee', 1, 1,
     'Apply at ircc.canada.ca or at the port of entry (CUSMA professionals only).',
     'Track application number; IRCC online processing typically 2–8 weeks for most exemptions.', 'ca_work_permit_submitted'),
    (gen_random_uuid(), _tid, 6, 'Work permit granted', 'employee', 1, 5,
     'Check permit conditions — it will specify employer, location, and expiry date.',
     'Retain copy; align start date with permit validity.', 'ca_work_permit_granted'),
    (gen_random_uuid(), _tid, 7, 'Social Insurance Number (SIN) obtained from Service Canada', 'employee', 1, 6,
     'Apply at a Service Canada centre with your work permit and passport. Required for payroll and tax filing.',
     'SIN required before first payroll — chase within first week of arrival.', 'ca_sin'),
    (gen_random_uuid(), _tid, 8, 'Provincial health insurance enrolled (or interim private insurance arranged)', 'employee', 0, NULL,
     'Most provinces have a 3-month waiting period — arrange private international health coverage from day one.',
     'Confirm employer provides interim private health cover for the waiting period.', 'ca_health'),
    (gen_random_uuid(), _tid, 9, 'Canadian bank account opened', 'employee', 0, NULL,
     'Required for salary deposit. Most major banks allow opening with passport and work permit.',
     'Required for salary payment; arrange before first pay date.', 'ca_bank_account');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Route determination & LMIA kick-off (if required)',
     'HR determines the correct work permit route. If LMIA is required, HR begins the ESDC application process.',
     'Confirm route; initiate LMIA if required — allow 2–5 months. For exempt routes, prepare supporting documentation.',
     'hr', 'T-16 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'LMIA granted / exempt route confirmed',
     'HR provides LMIA confirmation or exempt route documentation. You may now apply for the work permit.',
     'Issue LMIA and offer letter; guide employee through online work permit application.',
     'employer', 'T-8 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Work permit application submitted',
     'Apply online at ircc.canada.ca or at the port of entry (for CUSMA professionals).',
     'Track IRCC application reference; prepare for supplemental document requests.',
     'employee', 'T-6 weeks'),
    (gen_random_uuid(), _tid, 4, 'immigration', 'Work permit granted',
     'Check permit conditions, employer, and expiry date. Plan travel date.',
     'Retain copy; confirm start date; arrange private health insurance for 3-month waiting period.',
     'hr', 'T-2 to 4 weeks'),
    (gen_random_uuid(), _tid, 5, 'move', 'Arrival in Canada',
     'Enter Canada with your work permit approval letter and passport.',
     'Log arrival; initiate SIN and banking onboarding immediately.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 6, 'post', 'SIN, provincial health & banking',
     'Obtain SIN at Service Canada. Open a Canadian bank account. Register for provincial health insurance to start the waiting period clock.',
     'Confirm SIN on file before first payroll run; track provincial health waiting period.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 7, 'post', 'Settle-in complete',
     'Enrol children in school if applicable. Arrange rental contract. Set up provincial health insurance after waiting period.',
     'Schedule 3-month check-in; set work permit renewal reminder.',
     'hr', 'T+4 weeks');

  RAISE NOTICE 'CA readiness template inserted with id %', _tid;
END $$;
