-- ============================================================
-- DE (Germany) dossier questions — corrected re-seed.
-- ============================================================
-- Replay-safe replacement for 20260507150000_de_dossier_questions.sql, which
-- targeted phantom columns (destination/category/options_json/required/
-- applies_if_json) and aborted a fresh `supabase db reset` at SQLSTATE 42703.
--
-- Same 9 rows, same content, written into the table's REAL columns
-- (destination_country, domain, options, is_mandatory, applies_if) — identical
-- to the GB (20260507120000) and FR (20260507130000) seeds, and matching the 9
-- DE rows already on prod. Idempotent via ON CONFLICT on the unique index
-- (destination_country, question_key, version): a true no-op on prod.
-- See audit/migration-drift-definitive-2026-06-02.md § reverse-drift entry 10.
-- ============================================================

BEGIN;

INSERT INTO public.dossier_questions
  (destination_country, domain, question_key, question_text, answer_type,
   options, is_mandatory, applies_if, sort_order)
VALUES
  ('DE', 'immigration', 'de.visa_type_confirmed',
   'Has the work visa type been confirmed by your employer? (EU Blue Card or Skilled Worker Visa)',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   10),

  ('DE', 'immigration', 'de.qualifications_recognized',
   'Have your foreign professional qualifications been formally recognised by the relevant German authority?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   20),

  ('DE', 'immigration', 'de.consulate_appointment',
   'Has your appointment at the German consulate been booked for the visa application?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   30),

  ('DE', 'immigration', 'de.visa_submitted',
   'Has your visa application been submitted to the German consulate?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   40),

  ('DE', 'registration', 'de.anmeldung_completed',
   'Have you registered your address (Anmeldung) at the local Einwohnermeldeamt within 14 days of arrival?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   50),

  ('DE', 'immigration', 'de.aufenthaltstitel_submitted',
   'Has your residence permit (Aufenthaltstitel) application been submitted to the Ausländerbehörde?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   60),

  ('DE', 'insurance', 'de.health_insurance',
   'Do you have statutory or private health insurance in place? (Required for the residence permit application)',
   'boolean', NULL, FALSE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   70),

  ('DE', 'immigration', 'de.dependents',
   'Will any dependents (spouse, children) accompany you and require German visas or residence permits?',
   'boolean', NULL, FALSE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}',
   80),

  ('DE', 'immigration', 'de.dependent_details',
   'If yes, how many dependents will apply for German residence permits?',
   'text', NULL, FALSE,
   '{"field":"relocationBasics.hasDependents","op":"==","value":true}',
   90)
ON CONFLICT (destination_country, question_key, version) DO NOTHING;

COMMIT;
