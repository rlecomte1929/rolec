-- ============================================================
-- Sprint J: Add IT (Italy) dossier questions + readiness template
-- ============================================================

-- ── Dossier questions ─────────────────────────────────────────────────────────

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.nulla_osta') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'immigration', 'it.nulla_osta',
      'Has the Nulla Osta (work authorisation) been obtained from the Sportello Unico per l''Immigrazione?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.type_d_visa_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'immigration', 'it.type_d_visa_submitted',
      'Has the National (Type D) visa application been submitted at the Italian consulate?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.type_d_visa_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'immigration', 'it.type_d_visa_granted',
      'Has the Italian National (Type D) visa been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.permesso_soggiorno') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'immigration', 'it.permesso_soggiorno',
      'Has the Permesso di Soggiorno (residence permit) application been submitted to the Questura within 8 working days of arrival?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.codice_fiscale') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'registration', 'it.codice_fiscale',
      'Have you obtained your Italian tax code (Codice Fiscale) from the Agenzia delle Entrate?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.asl_enrollment') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'insurance', 'it.asl_enrollment',
      'Have you enrolled in the Italian national healthcare system (SSN/ASL)?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.residenza') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'registration', 'it.residenza',
      'Have you registered your Italian address at the local municipality (Residenza anagrafica)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 70);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'it.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IT', 'immigration', 'it.dependents',
      'Will any dependents accompany you and require Italian family visas or residence permits?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 80);
  END IF;

  RAISE NOTICE 'IT dossier questions seeded (idempotent).';
END $$;

-- ── Readiness template ────────────────────────────────────────────────────────

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'IT';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'IT readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Italy — Nulla Osta / National Visa + Permesso di Soggiorno',
    'Non-EU/EEA nationals require a Nulla Osta (work authorisation) from the Sportello Unico per l''Immigrazione, followed by a National (Type D) visa. Within 8 working days of arrival, you must submit a Permesso di Soggiorno application. All workers need a Codice Fiscale and Residenza registration.',
    'Nulla Osta is the critical path item for non-EU/EEA employees — apply via the Sportello Unico as soon as the job offer is confirmed, as processing can take 8–16 weeks. The 8-working-day Permesso window after arrival is legally strict.',
    'Italy''s Decreto Flussi annual quota may restrict some non-EU categories — confirm route availability. The Codice Fiscale is required for payroll, contracts, banking, and rental agreements.',
    '["Nulla Osta from the Sportello Unico can take 8–16 weeks — start immediately after job offer is confirmed.",
      "Permesso di Soggiorno application must be submitted within 8 working days of arrival — missing this creates irregular status.",
      "The kit receipt (ricevuta del kit postale) acts as temporary proof while the Permesso is processed (3–6 months).",
      "Codice Fiscale is required for payroll, contracts, banking, and leases — obtain it as soon as possible.",
      "Decreto Flussi annual quotas may restrict certain non-EU work categories — confirm route availability in advance."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Signed employment contract confirming role and salary', 'employer', 1, NULL,
     'Required for Nulla Osta application.',
     'Confirm salary meets EU Blue Card threshold (€32,000+) if applicable.', 'it_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Nulla Osta obtained from Sportello Unico per l''Immigrazione', 'employer', 1, 1,
     'Your employer files with the Sportello Unico. Processing: 8–16 weeks.',
     'Critical path — initiate the moment offer is confirmed. May fall under Decreto Flussi quota.', 'it_nulla_osta'),
    (gen_random_uuid(), _tid, 3, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for at least 3 months beyond intended stay.', NULL, 'it_passport'),
    (gen_random_uuid(), _tid, 4, 'National (Type D) visa application submitted at Italian consulate', 'employee', 1, 2,
     'Apply at the Italian consulate in your country of residence. Bring: Nulla Osta, passport, contract, photos, medical certificate.',
     'Lead time varies by consulate — book immediately after Nulla Osta is granted.', 'it_type_d_visa'),
    (gen_random_uuid(), _tid, 5, 'National (Type D) visa granted', 'employee', 1, 4,
     'Check validity window and permitted activities.',
     'Retain copy; align start date with visa validity.', 'it_type_d_granted'),
    (gen_random_uuid(), _tid, 6, 'Permesso di Soggiorno application submitted (within 8 working days of arrival)', 'employee', 1, 5,
     'Purchase and submit the kit at any post office (Poste Italiane) within 8 working days of arrival. Bring passport, visa, Nulla Osta, photos, and contract.',
     'Monitor the 8-day window strictly; retain kit receipt (ricevuta) as interim proof.', 'it_permesso_soggiorno'),
    (gen_random_uuid(), _tid, 7, 'Codice Fiscale obtained from Agenzia delle Entrate', 'employee', 1, NULL,
     'Apply at the Agenzia delle Entrate or Italian consulate abroad. Required for payroll, contracts, and banking.',
     'Obtain before first payroll run.', 'it_codice_fiscale'),
    (gen_random_uuid(), _tid, 8, 'Residenza anagrafica (address registration) at local municipality', 'employee', 1, NULL,
     'Register at your local Comune within 20 days of establishing residence.',
     'Required for some banking and public services.', 'it_residenza'),
    (gen_random_uuid(), _tid, 9, 'Healthcare enrollment (SSN/ASL) or private insurance', 'employee', 0, NULL,
     'Enrol in the Servizio Sanitario Nazionale (SSN) at your local ASL. Requires Codice Fiscale and Permesso di Soggiorno kit receipt.',
     'Confirm employer health benefit coverage from day one.', 'it_asl_enrollment');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Kickoff — Nulla Osta application',
     'HR initiates the Nulla Osta work authorisation request at the Sportello Unico. This is the critical path step.',
     'File with Sportello Unico immediately — processing takes 8–16 weeks. Confirm quota availability under Decreto Flussi.',
     'hr', 'T-16 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'Nulla Osta granted',
     'Work authorisation issued. Employer sends you the original document for the consulate application.',
     'Issue original Nulla Osta to employee; book consulate appointment immediately.',
     'employer', 'T-8 to 10 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Consulate appointment & Type D visa application',
     'Attend Italian consulate with full pack: Nulla Osta, passport, contract, photos, medical certificate.',
     'Track application; prepare for supplemental document requests.',
     'employee', 'T-6 to 8 weeks'),
    (gen_random_uuid(), _tid, 4, 'immigration', 'Type D visa granted',
     'Check visa validity. Plan entry date accordingly.',
     'Retain copy; update compliance record; confirm start date.',
     'hr', 'T-3 to 4 weeks'),
    (gen_random_uuid(), _tid, 5, 'move', 'Arrival & Permesso di Soggiorno kit',
     'Arrive in Italy. Within 8 working days, buy the Permesso di Soggiorno kit at Poste Italiane and submit your application. Keep the ricevuta as proof.',
     'Confirm arrival; monitor 8-day window; support with Poste Italiane visit if needed.',
     'employee', 'T-0 to T+8 days'),
    (gen_random_uuid(), _tid, 6, 'post', 'Codice Fiscale, Residenza & healthcare',
     'Obtain Codice Fiscale from Agenzia delle Entrate. Register Residenza at local Comune. Enrol in ASL healthcare.',
     'Confirm Codice Fiscale is on file before payroll run; schedule 3-month check-in.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 7, 'post', 'Permesso di Soggiorno issued & settle-in complete',
     'Collect Permesso di Soggiorno card (typically 3–6 months after application). Open bank account, finalise rental contract.',
     'File Permesso di Soggiorno copy; update renewal calendar (typically valid 2 years, then renewable).',
     'hr', 'T+12 to 24 weeks');

  RAISE NOTICE 'IT readiness template inserted with id %', _tid;
END $$;
