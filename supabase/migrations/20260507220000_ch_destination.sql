-- ============================================================
-- Sprint K: Add CH (Switzerland) dossier questions + readiness template
-- ============================================================

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ch.permit_type_confirmed') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CH', 'immigration', 'ch.permit_type_confirmed',
      'Has the Swiss residence/work permit type been confirmed with the cantonal migration office? (Permit L for short stay, B for annual stay)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ch.cantonal_permit_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CH', 'immigration', 'ch.cantonal_permit_submitted',
      'Has the cantonal migration office permit application been submitted by the employer?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ch.permit_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CH', 'immigration', 'ch.permit_granted',
      'Has the Swiss residence and work permit been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ch.commune_registration') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CH', 'registration', 'ch.commune_registration',
      'Have you registered your address at the local commune (Einwohnerkontrolle / contrôle des habitants) within 14 days of arrival?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ch.health_insurance') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CH', 'insurance', 'ch.health_insurance',
      'Is mandatory Swiss health insurance (Krankenkasse / assurance maladie) in place? (Required within 3 months of arrival)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ch.ahv_number') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CH', 'registration', 'ch.ahv_number',
      'Have you received your AHV/AVS social security number from the cantonal compensation office?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ch.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'CH', 'immigration', 'ch.dependents',
      'Will any dependents accompany you and require Swiss family reunion permits?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 70);
  END IF;

  RAISE NOTICE 'CH dossier questions seeded (idempotent).';
END $$;

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'CH';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'CH readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Switzerland — Residence & Work Permit (Permit L / B)',
    'Non-EU/EEA nationals require an employer-sponsored residence and work permit (Permit L for stays under 1 year, Permit B for stays of 1–5 years) issued by the cantonal migration office. EU/EEA nationals register directly under the Agreement on Free Movement of Persons. Mandatory Swiss health insurance must be arranged within 3 months of arrival.',
    'Non-EU/EEA permits are subject to annual cantonal and federal quotas — confirm availability before making an offer. The cantonal migration authority issues the permit; the employer sponsors it. Health insurance, AHV social security, and commune registration are mandatory post-arrival steps.',
    'Permit B (B-Bewilligung) is the standard annual permit for employed workers; renewable annually. Permit L is for short assignments under 12 months (not renewable). EU/EEA nationals register at the Einwohnerkontrolle with employer confirmation. Non-EU/EEA quota availability should be checked before offer stage.',
    '["Non-EU/EEA work permit quotas are limited per canton — check availability before making a job offer.",
      "Mandatory Swiss health insurance (Krankenkasse) must be arranged within 3 months of taking up residence.",
      "Address registration at the commune (Einwohnerkontrolle) must be completed within 14 days of arrival.",
      "AHV/AVS social security contributions are mandatory and deducted from payroll.",
      "Spouses of permit holders need their own permit application — apply in parallel."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Signed employment contract confirming role, salary, and start date', 'employer', 1, NULL,
     'Required for cantonal permit application.',
     'Salary must comply with Swiss standard of living; cantonal minimum wage thresholds apply.', 'ch_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Cantonal permit quota availability confirmed (non-EU/EEA)', 'employer', 1, 1,
     'Your employer will check with the cantonal migration authority whether a quota is available.',
     'EU/EEA nationals skip quota check. For non-EU/EEA, confirm quota before offer is extended.', 'ch_quota'),
    (gen_random_uuid(), _tid, 3, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for the intended permit period.', NULL, 'ch_passport'),
    (gen_random_uuid(), _tid, 4, 'Cantonal migration office permit application submitted', 'employer', 1, 2,
     'Your employer files with the cantonal migration office (Migrationsdienst/SMIG). Processing: 4–8 weeks.',
     'File immediately after quota confirmed. Include contract, diplomas, and employer declaration.', 'ch_permit_submitted'),
    (gen_random_uuid(), _tid, 5, 'Residence and work permit granted', 'employee', 1, 4,
     'You will receive a permit document to collect on arrival or at a Swiss mission.',
     'Retain permit copy; confirm start date; track permit expiry for renewal.', 'ch_permit_granted'),
    (gen_random_uuid(), _tid, 6, 'Address registered at commune (Einwohnerkontrolle)', 'employee', 1, 5,
     'Register within 14 days of arrival. Bring passport, permit, rental contract.',
     'Confirm registration — required for AHV enrollment and health insurance.', 'ch_commune_registration'),
    (gen_random_uuid(), _tid, 7, 'Mandatory health insurance (Krankenkasse) enrolled', 'employee', 1, NULL,
     'Arrange basic Swiss health insurance within 3 months of taking up residence. Retroactive premiums apply from first day if late.',
     'Confirm employee has enrolled; check if employer contributes to supplemental insurance.', 'ch_health_insurance'),
    (gen_random_uuid(), _tid, 8, 'AHV/AVS social security number received', 'employer', 1, 6,
     'Issued automatically via employer payroll registration. Required for pension contributions.',
     'Register employee with cantonal compensation office; AHV number needed before first payroll.', 'ch_ahv'),
    (gen_random_uuid(), _tid, 9, 'Swiss bank account opened', 'employee', 0, NULL,
     'Required for CHF salary. Most banks require permit and commune registration confirmation.',
     'Required for CHF salary payment.', 'ch_bank_account');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Quota check & permit application',
     'HR confirms quota availability for your nationality and files the cantonal permit application.',
     'Check quota with canton; initiate permit application immediately — processing 4–8 weeks.',
     'hr', 'T-10 weeks'),
    (gen_random_uuid(), _tid, 2, 'immigration', 'Permit granted',
     'Permit issued. You may now plan your move and travel date.',
     'Issue permit document to employee; confirm start date; set permit renewal reminder.',
     'hr', 'T-4 weeks'),
    (gen_random_uuid(), _tid, 3, 'move', 'Arrival & commune registration',
     'Arrive in Switzerland. Register your address at the commune (Einwohnerkontrolle) within 14 days.',
     'Confirm arrival and commune registration; initiate AHV enrollment and health insurance onboarding.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 4, 'post', 'Health insurance & AHV enrollment',
     'Arrange mandatory Krankenkasse health insurance within 3 months. Receive your AHV social security number via employer.',
     'Confirm health insurance enrollment; register AHV number before first payroll.',
     'employee', 'T+1 to 4 weeks'),
    (gen_random_uuid(), _tid, 5, 'post', 'Settle-in complete',
     'Open Swiss bank account. Register children in school. Note permit expiry for renewal.',
     'Schedule 3-month check-in; set permit renewal reminder (Permit B renewed annually).',
     'hr', 'T+6 to 8 weeks');

  RAISE NOTICE 'CH readiness template inserted with id %', _tid;
END $$;
