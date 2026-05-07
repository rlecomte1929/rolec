-- ============================================================
-- Sprint G: Add GB (UK Skilled Worker) dossier questions
-- ============================================================
-- Inserts the 8 UK-specific wizard Step-5 questions into
-- dossier_questions if they do not already exist.
-- Idempotent via ON CONFLICT DO NOTHING on the unique index
-- (destination_country, question_key, version).
-- ============================================================

BEGIN;

INSERT INTO public.dossier_questions
  (destination_country, domain, question_key, question_text, answer_type,
   options, is_mandatory, applies_if, sort_order)
VALUES
  ('GB', 'immigration', 'gb.sponsor_licence',
   'Does your employer hold an active UK Sponsor Licence issued by the Home Office?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}',
   10),

  ('GB', 'immigration', 'gb.cos_confirmed',
   'Has a Certificate of Sponsorship (CoS) been assigned to you by your employer?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}',
   20),

  ('GB', 'immigration', 'gb.salary_threshold',
   'Does your salary meet the Skilled Worker visa general threshold (£38,700 or SOC going rate, whichever is higher)?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}',
   30),

  ('GB', 'immigration', 'gb.points_eligibility',
   'Have the mandatory 70 points under the UK points-based system been confirmed? (Job offer 20 pts + sponsor 20 pts + salary 20 pts + English 10 pts)',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}',
   40),

  ('GB', 'immigration', 'gb.english_evidence',
   'Is English language evidence available? (degree taught in English, or approved test such as IELTS/LanguageCert)',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}',
   50),

  ('GB', 'registration', 'gb.move_date_confirm',
   'Do you have a confirmed arrival date in the UK?',
   'boolean', NULL, TRUE,
   '{"field":"relocationBasics.targetMoveDate","op":"exists","value":false}',
   60),

  ('GB', 'immigration', 'gb.dependents',
   'Will any dependents (spouse, children) accompany you and require a UK Dependant visa?',
   'boolean', NULL, FALSE,
   '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}',
   70),

  ('GB', 'immigration', 'gb.dependent_details',
   'If yes, how many dependents will apply for UK Dependant visas?',
   'text', NULL, FALSE,
   '{"field":"relocationBasics.hasDependents","op":"==","value":true}',
   80)

ON CONFLICT (destination_country, question_key, version) DO NOTHING;

COMMIT;
