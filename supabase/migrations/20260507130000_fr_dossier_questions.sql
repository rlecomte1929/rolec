-- ============================================================
-- Sprint H: Add FR (France) dossier questions
-- ============================================================
-- Inserts 8 France-specific wizard Step-5 questions into
-- dossier_questions if they do not already exist.
-- Idempotent via ON CONFLICT DO NOTHING on the unique index
-- (destination_country, question_key, version).
-- ============================================================

BEGIN;

INSERT INTO public.dossier_questions
  (destination_country, domain, question_key, question_text, answer_type,
   options, is_mandatory, applies_if, sort_order)
VALUES
  ('FR', 'immigration', 'fr.work_permit_route',
   'Has your employer confirmed the work permit route (Salarié or Passeport Talent)?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}',
   10),

  ('FR', 'immigration', 'fr.consulate_appointment',
   'Has your consulate appointment been booked for the long-stay visa application?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}',
   20),

  ('FR', 'immigration', 'fr.vls_ts_submitted',
   'Has your long-stay visa (VLS-TS) application been submitted to the consulate?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}',
   30),

  ('FR', 'immigration', 'fr.ofii_completed',
   'Have you completed the OFII arrival declaration and medical visit after entering France?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}',
   40),

  ('FR', 'immigration', 'fr.titre_sejour_scheduled',
   'Has your titre de séjour (residence permit) prefecture appointment been scheduled?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}',
   50),

  ('FR', 'housing', 'fr.housing_proof',
   'Do you have proof of housing available (signed lease or employer-provided accommodation)?',
   'boolean', NULL, FALSE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}',
   60),

  ('FR', 'immigration', 'fr.dependents',
   'Will any dependents (spouse, children) accompany you and require French visas or residency?',
   'boolean', NULL, FALSE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}',
   70),

  ('FR', 'immigration', 'fr.dependent_details',
   'If yes, how many dependents will apply for French residency documents?',
   'text', NULL, FALSE,
   '{"field":"relocationBasics.hasDependents","op":"==","value":true}',
   80)

ON CONFLICT (destination_country, question_key, version) DO NOTHING;

COMMIT;
