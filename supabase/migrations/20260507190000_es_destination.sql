-- ============================================================
-- Sprint J: Add ES (Spain) dossier questions + readiness template
-- ============================================================

-- ── Dossier questions ─────────────────────────────────────────────────────────

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.work_auth_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'immigration', 'es.work_auth_submitted',
      'Has the combined work and residence authorisation (autorización de residencia y trabajo) been applied for?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.visa_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'immigration', 'es.visa_granted',
      'Has the Spanish work/residence visa been granted at the consulate?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.nie_obtained') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'registration', 'es.nie_obtained',
      'Have you obtained your NIE (Número de Identidad de Extranjero) — the Spanish foreigner identification number?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.empadronamiento') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'registration', 'es.empadronamiento',
      'Have you completed the Empadronamiento (municipal address registration) at your local town hall (Ayuntamiento)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.tie_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'immigration', 'es.tie_submitted',
      'Has the TIE (Tarjeta de Identidad de Extranjero) residence card application been submitted to the Policía Nacional?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.social_security') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'registration', 'es.social_security',
      'Have you obtained your Spanish Social Security number (Número de Afiliación a la Seguridad Social)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.health_coverage') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'insurance', 'es.health_coverage',
      'Do you have access to Spanish public healthcare (via Social Security) or private health insurance?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 70);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'es.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'ES', 'immigration', 'es.dependents',
      'Will any dependents accompany you and require Spanish family residence visas?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 80);
  END IF;

  RAISE NOTICE 'ES dossier questions seeded (idempotent).';
END $$;

-- ── Readiness template ────────────────────────────────────────────────────────

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'ES';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'ES readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Spain — Work & Residence Authorisation / NIE / TIE',
    'Non-EU/EEA nationals require a combined work and residence authorisation (autorización de residencia y trabajo) filed by the employer in Spain, followed by a visa at the Spanish consulate. After arrival: obtain NIE, complete Empadronamiento, and apply for the TIE residence card within 30 days.',
    'The employer must file the work and residence authorisation application in Spain as the critical path step (allow 1–3 months). Ensure NIE, Empadronamiento, and TIE steps are completed promptly after arrival. Social Security registration must precede payroll.',
    'The autorización is issued by the immigration office (Delegación del Gobierno) in Spain. NIE is the core identifier for all Spanish official processes. TIE replaces the old green certificate for non-EU nationals. EU Blue Card route available for salaries ≥ 1.5× average salary.',
    '["The employer-filed work and residence authorisation can take 1–3 months — start immediately after offer is confirmed.",
      "NIE (Número de Identidad de Extranjero) is required for almost all Spanish official and commercial transactions.",
      "Empadronamiento (municipal registration) is required for healthcare access, school enrolment, and many administrative processes.",
      "TIE application must be submitted within 30 days of entering Spain on the work visa.",
      "Social Security number must be registered before payroll can run."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Signed employment contract', 'employer', 1, NULL,
     'Required for the work and residence authorisation application.',
     'Confirm contract specifies role, salary, and work location in Spain.', 'es_offer_letter'),
    (gen_random_uuid(), _tid, 2, 'Work and residence authorisation (autorización de residencia y trabajo) filed', 'employer', 1, 1,
     'Your employer files with the Delegación del Gobierno in Spain. Allow 1–3 months.',
     'Critical path — initiate immediately after offer is signed. Track expediente number.', 'es_work_auth'),
    (gen_random_uuid(), _tid, 3, 'Work and residence authorisation granted', 'employer', 1, 2,
     'Employer receives resolution; you can then apply for the visa at the Spanish consulate.',
     'Send resolution to employee promptly; consulate step must follow within validity window.', 'es_work_auth_granted'),
    (gen_random_uuid(), _tid, 4, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for at least 1 year beyond the intended stay.', NULL, 'es_passport'),
    (gen_random_uuid(), _tid, 5, 'Spanish work/residence visa obtained at consulate', 'employee', 1, 3,
     'Apply at the Spanish consulate in your country of residence with the authorisation resolution.',
     'The visa is typically valid for 90 days entry — must be used within this window.', 'es_visa_granted'),
    (gen_random_uuid(), _tid, 6, 'NIE (Número de Identidad de Extranjero) obtained', 'employee', 1, NULL,
     'Apply at the local Policía Nacional comisaría or via consulate. Required for all official and commercial transactions in Spain.',
     'NIE is the key identifier — payroll, bank accounts, and lease agreements all require it.', 'es_nie'),
    (gen_random_uuid(), _tid, 7, 'Empadronamiento (municipal address registration) completed', 'employee', 1, NULL,
     'Register at your local Ayuntamiento with passport, visa, and rental contract. Required for healthcare and school enrolment.',
     'Confirm registration; needed for healthcare access from day one.', 'es_empadronamiento'),
    (gen_random_uuid(), _tid, 8, 'TIE (Tarjeta de Identidad de Extranjero) residence card application submitted', 'employee', 1, 6,
     'Apply at the Policía Nacional within 30 days of entering Spain. Bring: passport, visa, NIE, Empadronamiento certificate, photos, and employment contract.',
     'Retain appointment receipt as interim proof; TIE takes 4–6 weeks to issue.', 'es_tie'),
    (gen_random_uuid(), _tid, 9, 'Social Security number (Número de Afiliación) registered', 'employer', 1, NULL,
     'Your employer registers you with the INSS (Instituto Nacional de la Seguridad Social) before your first working day.',
     'Required before payroll — employer registers affiliation number at INSS.', 'es_social_security');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Kickoff — work and residence authorisation application',
     'HR files the work and residence authorisation with the Delegación del Gobierno in Spain. This is the critical path step.',
     'File autorización de residencia y trabajo immediately — processing can take 1–3 months.',
     'hr', 'T-14 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'Authorisation granted',
     'HR sends you the resolution. Book your consulate appointment promptly — the resolution has a validity window.',
     'Send resolution to employee; ensure they book consulate within validity window.',
     'employer', 'T-8 to 10 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'Consulate appointment & visa obtained',
     'Visit Spanish consulate with resolution, passport, photos, and supporting documents. Collect visa.',
     'Track visa collection; confirm planned entry date.',
     'employee', 'T-6 to 8 weeks'),
    (gen_random_uuid(), _tid, 4, 'move', 'Arrival in Spain',
     'Enter Spain. The 30-day TIE application window starts from entry.',
     'Log arrival date; set TIE 30-day reminder immediately.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 5, 'post', 'NIE, Empadronamiento & Social Security',
     'Obtain NIE at Policía Nacional. Complete Empadronamiento at Ayuntamiento. Employer registers your Social Security affiliation (INSS).',
     'Confirm NIE and Social Security number on file before first payroll run.',
     'employee', 'T+1 to 2 weeks'),
    (gen_random_uuid(), _tid, 6, 'post', 'TIE application submitted',
     'Apply for TIE (residence card) at Policía Nacional within 30 days of entry. Retain appointment receipt as interim proof.',
     'File appointment receipt; TIE card typically issued in 4–6 weeks.',
     'employee', 'T+2 to 4 weeks'),
    (gen_random_uuid(), _tid, 7, 'post', 'TIE received & settle-in complete',
     'Collect TIE card. Open Spanish bank account. Enrol children in school if applicable.',
     'File TIE copy; update TIE renewal calendar (typically valid 1–2 years, then renewable); confirm payroll and healthcare active.',
     'hr', 'T+6 to 8 weeks');

  RAISE NOTICE 'ES readiness template inserted with id %', _tid;
END $$;
