-- ============================================================
-- Sprint I: Add DE (Germany) dossier questions
-- ============================================================

DO $$
BEGIN

  -- 1. Visa type confirmed (Blue Card vs Skilled Worker)
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.visa_type_confirmed'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'immigration', 'de.visa_type_confirmed',
       'Has the work visa type been confirmed by your employer? (EU Blue Card or Skilled Worker Visa)',
       'boolean', NULL, TRUE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 10);
  END IF;

  -- 2. Qualifications recognised
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.qualifications_recognized'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'immigration', 'de.qualifications_recognized',
       'Have your foreign professional qualifications been formally recognised by the relevant German authority?',
       'boolean', NULL, TRUE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 20);
  END IF;

  -- 3. Consulate appointment booked
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.consulate_appointment'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'immigration', 'de.consulate_appointment',
       'Has your appointment at the German consulate been booked for the visa application?',
       'boolean', NULL, TRUE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 30);
  END IF;

  -- 4. Visa application submitted
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.visa_submitted'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'immigration', 'de.visa_submitted',
       'Has your visa application been submitted to the German consulate?',
       'boolean', NULL, TRUE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 40);
  END IF;

  -- 5. Anmeldung completed
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.anmeldung_completed'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'registration', 'de.anmeldung_completed',
       'Have you registered your address (Anmeldung) at the local Einwohnermeldeamt within 14 days of arrival?',
       'boolean', NULL, TRUE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 50);
  END IF;

  -- 6. Aufenthaltstitel submitted
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.aufenthaltstitel_submitted'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'immigration', 'de.aufenthaltstitel_submitted',
       'Has your residence permit (Aufenthaltstitel) application been submitted to the Ausländerbehörde?',
       'boolean', NULL, TRUE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 60);
  END IF;

  -- 7. Health insurance in place
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.health_insurance'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'insurance', 'de.health_insurance',
       'Do you have statutory or private health insurance in place? (Required for the residence permit application)',
       'boolean', NULL, FALSE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 70);
  END IF;

  -- 8. Dependents
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.dependents'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'immigration', 'de.dependents',
       'Will any dependents (spouse, children) accompany you and require German visas or residence permits?',
       'boolean', NULL, FALSE,
       '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 80);
  END IF;

  -- 9. Dependent details (conditional)
  IF NOT EXISTS (
    SELECT 1 FROM dossier_questions WHERE question_key = 'de.dependent_details'
  ) THEN
    INSERT INTO dossier_questions
      (id, destination, category, question_key, question_text,
       answer_type, options_json, required, applies_if_json, sort_order)
    VALUES
      (gen_random_uuid(), 'DE', 'immigration', 'de.dependent_details',
       'If yes, how many dependents will apply for German residence permits?',
       'text', NULL, FALSE,
       '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 90);
  END IF;

  RAISE NOTICE 'DE dossier questions seeded (idempotent).';

END $$;
