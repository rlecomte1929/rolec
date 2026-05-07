-- ============================================================
-- Sprint J: Add NO (Norway) dossier questions + readiness template
-- ============================================================

-- ── Dossier questions ─────────────────────────────────────────────────────────

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.permit_type_confirmed') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'immigration', 'no.permit_type_confirmed',
      'Has the work authorisation type been confirmed? (Skilled Worker Permit for non-EU/EEA, or Registration Certificate for EU/EEA nationals)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.udi_application_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'immigration', 'no.udi_application_submitted',
      'Has the Skilled Worker Permit application been submitted to UDI (Utlendingsdirektoratet)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.permit_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'immigration', 'no.permit_granted',
      'Has the Norwegian work permit or EEA registration certificate been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.d_number') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'registration', 'no.d_number',
      'Have you obtained a Norwegian D-number or national identity number (fødselsnummer) from Skatteetaten?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.skattekort') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'registration', 'no.skattekort',
      'Have you obtained your tax card (Skattekort) from Skatteetaten? (Required before first payroll — without it 50% tax is withheld)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.folkeregisteret') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'registration', 'no.folkeregisteret',
      'Have you registered your Norwegian address with the National Population Register (Folkeregisteret)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.health_coverage') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'insurance', 'no.health_coverage',
      'Are you enrolled in the Norwegian National Insurance Scheme (Folketrygden) or do you have private health coverage?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 70);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'immigration', 'no.dependents',
      'Will any dependents (spouse, children) accompany you and require Norwegian family immigration permits?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 80);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'no.dependent_details') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'NO', 'immigration', 'no.dependent_details',
      'If yes, how many dependents will apply for Norwegian family immigration permits?',
      'text', NULL, FALSE,
      '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 90);
  END IF;

  RAISE NOTICE 'NO dossier questions seeded (idempotent).';
END $$;

-- ── Readiness template ────────────────────────────────────────────────────────

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'NO';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'NO readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Norway — Skilled Worker Permit / EEA Registration',
    'Non-EU/EEA nationals need a Skilled Worker Permit (faglært arbeidstillatelse) applied through UDI. EU/EEA nationals register a certificate of residence at Statsforvalteren. Both groups need a tax card (Skattekort) and Folkeregisteret address registration before payroll can run.',
    'Confirm nationality to choose the correct route. Initiate UDI application as soon as the job offer is signed — processing times vary from 1–12 weeks. Ensure Skattekort and Folkeregisteret steps are completed before first pay date.',
    'Skilled Worker Permit requires a concrete job offer at Norwegian standard salary. D-number is issued first; fødselsnummer comes after 6 months of registered residence.',
    '["UDI processing for Skilled Worker Permits can take 1–12 weeks — apply immediately after job offer is signed.",
      "Skattekort must be obtained before first payroll run; delays cause higher withholding tax (50%).",
      "Folkeregisteret address registration must be done within 8 days of establishing residence.",
      "D-number is issued for short stays; fødselsnummer after 6 months — bank accounts often require the latter."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Signed employment contract confirming salary and role', 'employer', 1, NULL,
     'Required for UDI application and Skattekort.', 'Confirm salary meets Norwegian standard market rate.', 'no_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for the intended duration of stay.', NULL, 'no_passport'),
    (gen_random_uuid(), _tid, 3, 'UDI permit application submitted (non-EU/EEA) or EEA registration (EU/EEA)', 'employee', 1, 1,
     'Non-EU/EEA: apply at udi.no. EU/EEA: register at Statsforvalteren within 3 months.',
     'Track UDI reference number; processing time 1–12 weeks.', 'no_udi_application'),
    (gen_random_uuid(), _tid, 4, 'Work permit / EEA registration certificate granted', 'employee', 1, 3,
     'Check permit validity dates and conditions before travelling.',
     'Retain copy for HR file; confirm permitted start date.', 'no_permit_granted'),
    (gen_random_uuid(), _tid, 5, 'D-number or fødselsnummer obtained from Skatteetaten', 'employee', 1, NULL,
     'Apply at Skatteetaten or tax office. D-number issued within days; fødselsnummer after 6 months.',
     'Required for Skattekort and Folkeregisteret registration.', 'no_d_number'),
    (gen_random_uuid(), _tid, 6, 'Tax card (Skattekort) obtained', 'employee', 1, 5,
     'Obtain at skatteetaten.no before first payroll — without it, 50% tax is withheld.',
     'Payroll cannot run correctly without Skattekort on file.', 'no_skattekort'),
    (gen_random_uuid(), _tid, 7, 'Address registered with Folkeregisteret (Norwegian Population Register)', 'employee', 1, NULL,
     'Register within 8 days of establishing Norwegian residence. Bring housing contract.',
     'Confirm registration so fødselsnummer conversion can be triggered at 6 months.', 'no_folkeregisteret'),
    (gen_random_uuid(), _tid, 8, 'Norwegian bank account opened', 'employee', 0, NULL,
     'Most banks require D-number or fødselsnummer; some accept passport for initial account.',
     'Required for salary payment to Norwegian account.', 'no_bank_account'),
    (gen_random_uuid(), _tid, 9, 'Housing & schooling shortlist (if family)', 'employee', 0, NULL,
     'Family members require separate immigration applications — apply in parallel.',
     'Confirm relocation budget covers family costs.', 'no_housing_school');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Kickoff & permit route confirmation',
     'HR confirms whether you need a UDI Skilled Worker Permit (non-EU/EEA) or EEA registration certificate (EU/EEA) and outlines the timeline.',
     'Verify nationality and choose route; initiate UDI application immediately after offer is signed.',
     'hr', 'T-12 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'UDI application / EEA registration submitted',
     'Submit Skilled Worker Permit application via udi.no, or gather documents for EEA registration.',
     'Track reference number; processing can take 1–12 weeks for Skilled Worker Permits.',
     'employee', 'T-10 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Permit granted',
     'Check permit validity and conditions. Confirm entry date with HR.',
     'Retain permit copy; update compliance record; confirm start date.',
     'hr', 'T-4 to 6 weeks'),
    (gen_random_uuid(), _tid, 4, 'move', 'Arrival & address registration',
     'Arrive in Norway and register your address with Folkeregisteret within 8 days. Bring housing contract.',
     'Confirm arrival and registration; schedule Skatteetaten visit.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 5, 'post', 'D-number, Skattekort & bank account',
     'Obtain D-number from Skatteetaten, then immediately apply for Skattekort to avoid 50% withholding tax. Open bank account.',
     'Confirm Skattekort is on file before first payroll run.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 6, 'post', 'Settle-in complete',
     'Enrol in Folketrygden (National Insurance), register dependants if applicable, schedule 3-month check-in.',
     'Confirm all registrations complete; schedule fødselsnummer transition at 6 months.',
     'hr', 'T+4 weeks');

  RAISE NOTICE 'NO readiness template inserted with id %', _tid;
END $$;
