-- ============================================================
-- Sprint I: Add DE (Germany) readiness template
-- ============================================================

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'DE';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
  _existing UUID;
BEGIN

  SELECT id INTO _existing
    FROM readiness_templates
   WHERE destination_key = _dest AND route_key = _route
   LIMIT 1;

  IF _existing IS NOT NULL THEN
    RAISE NOTICE 'DE readiness template already exists – skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates
    (id, destination_key, route_key, route_title,
     employee_summary, hr_summary, internal_notes_hr,
     watchouts_json, updated_at)
  VALUES
    (_tid, _dest, _route,
     'Germany — EU Blue Card / Skilled Worker Visa',
     'Your employer will sponsor either an EU Blue Card (for high earners) or a Skilled Worker Visa under Germany''s Fachkräftezuwanderungsgesetz. You apply at the German consulate before travelling, then complete Anmeldung and the residence permit after arrival.',
     'Confirm visa route based on salary and qualification recognition status. Support the employee''s consulate application and ensure Anmeldung and Ausländerbehörde steps are completed promptly after arrival.',
     'EU Blue Card requires salary ≥ €45,300 (2024 threshold) or €56,400 for shortage occupations. Qualification recognition may take 4–12 weeks — start early. Anmeldung must be done within 14 days of arrival.',
     '["Qualification recognition (Anerkennung) can be the critical-path item — initiate before the consulate appointment.",
       "Anmeldung must be completed within 14 days of arrival; the Anmeldebestätigung is needed for the Aufenthaltstitel and bank accounts.",
       "Statutory health insurance must be in place before the Ausländerbehörde appointment.",
       "EU Blue Card holders can bring family without a separate income threshold."]',
     _now
    );

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required,
     depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1,
     'Signed employment contract confirming salary and role',
     'employer', 1, NULL,
     'Required for visa application and qualification recognition.',
     'Confirm salary meets Blue Card or Skilled Worker threshold.',
     'de_offer_letter'),

    (gen_random_uuid(), _tid, 2,
     'Professional qualification recognition (Anerkennung)',
     'employee', 1, NULL,
     'Submit via anabin database or relevant chamber. Allow 4–12 weeks.',
     'Required for regulated professions and Blue Card applications.',
     'de_qualification_recognition'),

    (gen_random_uuid(), _tid, 3,
     'Valid passport (all travellers)',
     'employee', 1, NULL,
     'Must be valid for at least 6 months beyond intended stay.',
     NULL,
     'de_passport'),

    (gen_random_uuid(), _tid, 4,
     'Consulate appointment booked',
     'employee', 1, NULL,
     'Book at the German consulate in your current country of residence.',
     'Lead time varies by consulate — book at T-12 weeks.',
     'de_consulate_appointment'),

    (gen_random_uuid(), _tid, 5,
     'Visa application submitted',
     'employee', 1, 4,
     'Bring full document pack: passport, contract, qualifications, biometric photos, health insurance proof.',
     'Track application reference number.',
     'de_visa_application'),

    (gen_random_uuid(), _tid, 6,
     'Visa granted',
     'employee', 1, 5,
     'Check visa validity dates and permitted activities.',
     'Retain copy for HR file.',
     'de_visa_granted'),

    (gen_random_uuid(), _tid, 7,
     'Anmeldung (address registration) completed',
     'employee', 1, 6,
     'Register at the local Einwohnermeldeamt within 14 days of arrival. Bring passport and rental contract.',
     'Anmeldebestätigung is needed for bank account and Ausländerbehörde.',
     'de_anmeldung'),

    (gen_random_uuid(), _tid, 8,
     'Statutory or private health insurance enrolled',
     'employee', 1, NULL,
     'Must be in place before the Ausländerbehörde appointment.',
     'Check employer''s health insurance contribution obligations.',
     'de_health_insurance'),

    (gen_random_uuid(), _tid, 9,
     'Residence permit (Aufenthaltstitel) application submitted',
     'employee', 1, 7,
     'Apply at the Ausländerbehörde. Bring: passport, Anmeldebestätigung, contract, health insurance proof.',
     'Process can take 4–8 weeks; employee may work in the meantime if visa permits.',
     'de_aufenthaltstitel'),

    (gen_random_uuid(), _tid, 10,
     'Housing & schooling shortlist (if family)',
     'employee', 0, NULL,
     'Family members need separate Aufenthaltstitel — apply at the same time.',
     'Confirm relocation budget covers family costs.',
     'de_housing_school');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title,
     body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre',
     'Kickoff & visa route confirmation',
     'HR confirms whether you qualify for the EU Blue Card or Skilled Worker Visa and outlines the timeline.',
     'Verify salary vs Blue Card threshold; initiate qualification recognition if needed.',
     'hr', 'T-14 weeks'),

    (gen_random_uuid(), _tid, 2, 'pre',
     'Qualification recognition submitted',
     'Submit your qualifications to the relevant German authority (anabin, IHK, or professional chamber).',
     'Track recognition status — this is often the critical path.',
     'employee', 'T-12 weeks'),

    (gen_random_uuid(), _tid, 3, 'pre',
     'Document pack ready & consulate booked',
     'Gather passport, contract, qualification recognition, biometric photos, and health insurance evidence.',
     'Review pack for completeness before consulate appointment.',
     'employee', 'T-10 weeks'),

    (gen_random_uuid(), _tid, 4, 'immigration',
     'Consulate appointment & visa application',
     'Attend consulate with full document pack and submit visa application.',
     'Track application reference; prepare for any additional document requests.',
     'employee', 'T-8 weeks'),

    (gen_random_uuid(), _tid, 5, 'immigration',
     'Visa granted',
     'Check visa validity dates. First entry must be within the validity window.',
     'File copy; update compliance record; coordinate start date.',
     'hr', 'T-4 weeks'),

    (gen_random_uuid(), _tid, 6, 'move',
     'Arrival & Anmeldung',
     'Arrive in Germany and register your address (Anmeldung) within 14 days at the Einwohnermeldeamt.',
     'Confirm arrival and Anmeldung completion; support with rental contract if needed.',
     'employee', 'T-0'),

    (gen_random_uuid(), _tid, 7, 'post',
     'Aufenthaltstitel & settle-in',
     'Apply for residence permit at Ausländerbehörde. Open bank account, enroll in health insurance, register with tax office.',
     'Confirm Aufenthaltstitel submitted; schedule 3-month check-in.',
     'employee', 'T+2 to 4 weeks');

  RAISE NOTICE 'DE readiness template inserted with id %', _tid;

END $$;
