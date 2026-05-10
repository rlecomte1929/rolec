-- ============================================================
-- Sprint J: Add BR (Brazil) dossier questions + readiness template
-- ============================================================

-- ── Dossier questions ─────────────────────────────────────────────────────────

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.mte_authorization') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'immigration', 'br.mte_authorization',
      'Has the employer obtained work authorisation approval from the Ministry of Labour (SINFRE/MTE)?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.consulate_appointment') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'immigration', 'br.consulate_appointment',
      'Has a consulate appointment been booked for the VITEM V (temporary worker) visa application?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.vitem_v_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'immigration', 'br.vitem_v_submitted',
      'Has the VITEM V work visa application been submitted at the Brazilian consulate?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.vitem_v_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'immigration', 'br.vitem_v_granted',
      'Has the VITEM V work visa been granted?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.crnm_registered') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'immigration', 'br.crnm_registered',
      'Has the CRNM (Carteira de Registro Nacional Migratório) been registered at the Federal Police within 90 days of arrival?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.cpf_registered') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'registration', 'br.cpf_registered',
      'Has your CPF (Cadastro de Pessoas Físicas) tax ID number been registered with Receita Federal?',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.health_insurance') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'insurance', 'br.health_insurance',
      'Do you have Brazilian private health insurance (plano de saúde) in place?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 70);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'br.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'BR', 'immigration', 'br.dependents',
      'Will any dependents accompany you and require Brazilian visas or residency documents?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 80);
  END IF;

  RAISE NOTICE 'BR dossier questions seeded (idempotent).';
END $$;

-- ── Readiness template ────────────────────────────────────────────────────────

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'BR';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'BR readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Brazil — VITEM V Work Visa / CRNM',
    'Your employer must first obtain work authorisation from Brazil''s Ministry of Labour (SINFRE/MTE), which unlocks your VITEM V (temporary worker) visa at the consulate. After arrival, you must register with the Federal Police within 90 days to obtain your CRNM and then obtain a CPF (tax ID) with Receita Federal.',
    'Initiate the MTE employer authorisation as the critical path item — this can take 4–8 weeks before the employee can apply at the consulate. Ensure CRNM and CPF steps are completed within 90 days of arrival.',
    'VITEM V is the standard route for employed workers. The CRNM replaces the old RNE card. CPF is required for bank accounts, payroll, and any Brazilian contracts. CTPS (Carteira de Trabalho) digital registration with the employer is also required.',
    '["Ministry of Labour (MTE/SINFRE) authorisation is the critical path — allow 4–8 weeks before consulate application.",
      "CRNM Federal Police registration must be completed within 90 days of first entry or legal status lapses.",
      "CPF (Cadastro de Pessoas Físicas) is required for payroll, bank accounts, and almost all official transactions.",
      "Private health insurance is strongly recommended; public SUS access for non-citizens can be limited."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1, 'Ministry of Labour (MTE/SINFRE) work authorisation obtained', 'employer', 1, NULL,
     'Your employer applies via SINFRE. Allow 4–8 weeks.', 'Critical path item — start immediately after offer is confirmed.', 'br_mte_authorization'),
    (gen_random_uuid(), _tid, 2, 'Signed employment contract (CLT or assignment agreement)', 'employer', 1, NULL,
     'Required for MTE application and consulate visa.', 'Specify contract type — CLT (direct hire) or assignment/secondment.', 'br_offer_letter'),
    (gen_random_uuid(), _tid, 3, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must be valid for at least 6 months beyond intended stay.', NULL, 'br_passport'),
    (gen_random_uuid(), _tid, 4, 'Consulate appointment booked for VITEM V', 'employee', 1, 1,
     'Book at the Brazilian consulate in your country of residence after MTE authorisation is granted.',
     'Lead time varies by consulate — book at T-8 weeks.', 'br_consulate_appointment'),
    (gen_random_uuid(), _tid, 5, 'VITEM V visa application submitted', 'employee', 1, 4,
     'Bring: passport, MTE authorisation, employment contract, biometric photos, police clearance certificate.',
     'Track application; prepare for additional document requests.', 'br_vitem_v_submitted'),
    (gen_random_uuid(), _tid, 6, 'VITEM V visa granted', 'employee', 1, 5,
     'Check validity dates and entry conditions. First entry must be within validity window.',
     'Retain copy for HR file; confirm planned entry date.', 'br_vitem_v_granted'),
    (gen_random_uuid(), _tid, 7, 'CRNM registration at Federal Police (within 90 days of arrival)', 'employee', 1, 6,
     'Register at the nearest Federal Police (Polícia Federal) unit with passport, visa, photos, and employment contract. Do not miss the 90-day deadline.',
     'Monitor 90-day clock from arrival date; delays result in fines and irregular status.', 'br_crnm'),
    (gen_random_uuid(), _tid, 8, 'CPF (Cadastro de Pessoas Físicas) registered with Receita Federal', 'employee', 1, NULL,
     'Apply at a Receita Federal office or Banco do Brasil branch. Required for bank account and payroll.',
     'CPF is needed before payroll can run legally.', 'br_cpf'),
    (gen_random_uuid(), _tid, 9, 'Private health insurance enrolled', 'employee', 0, NULL,
     'Public SUS access may be limited — private plano de saúde is strongly recommended.',
     'Check whether employer provides health plan; confirm coverage starts from first day.', 'br_health_insurance');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre', 'Kickoff — MTE employer authorisation',
     'HR initiates the work authorisation request with Brazil''s Ministry of Labour (SINFRE/MTE). This is the critical-path step.',
     'File MTE application immediately — 4–8 week process before consulate can be approached.',
     'hr', 'T-14 weeks'),
    (gen_random_uuid(), _tid, 2, 'pre', 'MTE authorisation granted & consulate booked',
     'MTE authorisation letter received. Book consulate appointment for VITEM V application.',
     'Issue authorisation document to employee; track consulate booking.',
     'employee', 'T-10 weeks'),
    (gen_random_uuid(), _tid, 3, 'immigration', 'VITEM V application submitted',
     'Attend consulate with full document pack: passport, MTE authorisation, contract, photos, police clearance.',
     'Track application reference; prepare for supplemental document requests.',
     'employee', 'T-8 weeks'),
    (gen_random_uuid(), _tid, 4, 'immigration', 'VITEM V visa granted',
     'Check validity window. Plan entry date to align with start date.',
     'Retain visa copy; update compliance record; align start date.',
     'hr', 'T-4 weeks'),
    (gen_random_uuid(), _tid, 5, 'move', 'Arrival in Brazil',
     'Enter Brazil. The 90-day clock for CRNM Federal Police registration starts from first entry.',
     'Log arrival date; set CRNM 90-day reminder immediately.',
     'employee', 'T-0'),
    (gen_random_uuid(), _tid, 6, 'post', 'Federal Police CRNM registration',
     'Visit the Federal Police (Polícia Federal) with passport, VITEM V visa, photos, and employment contract. Obtain CRNM card.',
     'Confirm CRNM completed well before 90-day deadline to avoid fines.',
     'employee', 'T+4 to 8 weeks'),
    (gen_random_uuid(), _tid, 7, 'post', 'CPF, CTPS & settle-in',
     'Register CPF at Receita Federal. Confirm CTPS digital registration with employer. Open bank account. Enrol in health plan.',
     'Confirm CPF and CTPS on file before first payroll run; schedule 3-month check-in.',
     'employee', 'T+2 to 4 weeks');

  RAISE NOTICE 'BR readiness template inserted with id %', _tid;
END $$;
