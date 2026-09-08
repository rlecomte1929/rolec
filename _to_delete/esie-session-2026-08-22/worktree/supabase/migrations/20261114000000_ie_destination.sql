-- ============================================================
-- [AIQ-1868] Add IE (Ireland) dossier questions + readiness template
-- ============================================================
--
-- HR's case summary showed, on every Madrid->Dublin case:
--   "No verified readiness template is configured for destination 'IE' and
--    route 'employment'. Human review required."
-- (backend/provenance_catalog.py, degraded_readiness_payload reason='no_template')
--
-- Verified in prod 2026-08-20: readiness_templates carries an `employment` row for
-- AE, AU, BR, CA, CH, DE, ES, FR, GB, HK, IT, JP, NL, NO, SG and ZA — sixteen
-- destinations, and no IE. Ireland is sellable in the destination catalog but
-- reads as an unconfigured corridor to HR.
--
-- Mirrors 20260507160000_no_destination.sql exactly (the FR/DE/NO pattern the
-- ticket names). Content only — no schema change. Idempotent: dossier questions
-- are guarded per question_key, the template on (destination_key, route_key).
--
-- The human-review fallback is untouched: destinations with no template still
-- degrade exactly as before. This adds one row; it does not weaken the guard.
--
-- ONE TEMPLATE, TWO NATIONALITY BRANCHES. readiness_templates is keyed on
-- (destination, route) with no nationality dimension, so every string below is
-- written to be true for BOTH branches — the same shape the NO template uses.
-- For Ireland the split is unusually wide and getting it wrong is expensive:
--   * EU/EEA/Swiss  — no permit, no visa, and NO residence registration at all.
--   * non-EEA       — employment permit BEFORE travel, a long-stay 'D' visa if
--                     visa-required, then IRP registration within 90 days.
--
-- Two facts most third-party guides still get wrong, so both are stated:
--   * Ireland is NOT in the EU Blue Card scheme — it uses employment permits.
--   * Ireland is NOT in the Schengen area — a Spanish residence permit confers
--     no right to enter Ireland.
--   * DETE's Trusted Partner Initiative is discontinued (folded into Employment
--     Permits Online); guides still advertising it as a fast-track are stale.

-- ── Dossier questions ─────────────────────────────────────────────────────────

DO $$
BEGIN

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.permit_route_confirmed') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'immigration', 'ie.permit_route_confirmed',
      'Has the immigration route been confirmed? (EU/EEA/Swiss nationals need nothing; other nationals need a Critical Skills or General Employment Permit)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 10);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.employment_permit_submitted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'immigration', 'ie.employment_permit_submitted',
      'For non-EEA nationals: has the employment permit application been submitted to DETE via Employment Permits Online? (Must be RECEIVED at least 12 weeks before the intended start date)',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 20);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.employment_permit_granted') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'immigration', 'ie.employment_permit_granted',
      'For non-EEA nationals: has the employment permit been granted?',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 30);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.long_stay_visa') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'immigration', 'ie.long_stay_visa',
      'For visa-required nationals: has the long-stay ''D'' employment visa been applied for at the Irish embassy in the country of residence? (Ireland is outside Schengen — an EU residence permit gives no entry right)',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 40);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.ppsn') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'registration', 'ie.ppsn',
      'Has a PPS number (PPSN) been obtained? (Applies to every nationality. Apply on MyWelfare.ie; a mandatory in-person appointment follows)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 50);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.revenue_job_registered') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'registration', 'ie.revenue_job_registered',
      'Has the employment been registered by the employee in Revenue myAccount? (The employer cannot do this. Without it, emergency tax reaches 40% income tax plus USC from week 5)',
      'boolean', NULL, TRUE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 60);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.irp_registration') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'registration', 'ie.irp_registration',
      'For non-EEA nationals only: has the Irish Residence Permit (IRP) been registered within 90 days of arrival? (First-time registration is at Burgh Quay, Dublin; EUR 300. EU/EEA/Swiss nationals do NOT register at all)',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 70);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key = 'ie.dependents') THEN
    INSERT INTO dossier_questions (id, destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
    VALUES (gen_random_uuid(), 'IE', 'immigration', 'ie.dependents',
      'Will any dependants (spouse, children) accompany the employee? (A Critical Skills permit holder''s spouse is granted Stamp 1G on registration and may work without a separate permit)',
      'boolean', NULL, FALSE,
      '{"field":"relocationBasics.destCountry","op":"in","value":["Ireland","IE","Dublin"]}', 80);
  END IF;

  RAISE NOTICE 'IE dossier questions seeded (idempotent).';
END $$;

-- ── Readiness template ────────────────────────────────────────────────────────

DO $$
DECLARE
  _tid TEXT := gen_random_uuid()::text;
  _dest TEXT := 'IE';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
BEGIN
  IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route) THEN
    RAISE NOTICE 'IE readiness template already exists - skipping.';
    RETURN;
  END IF;

  INSERT INTO readiness_templates (id, destination_key, route_key, route_title, employee_summary, hr_summary, internal_notes_hr, watchouts_json, updated_at)
  VALUES (_tid, _dest, _route,
    'Ireland - Employment Permit (non-EEA) / free movement (EU-EEA-Swiss)',
    'If you are an EU, EEA or Swiss citizen you need no permit, no visa and no residence registration to work in Ireland - there is no Irish equivalent of a German Anmeldung. If you hold another nationality you need an employment permit from DETE before you travel, a long-stay ''D'' visa if your nationality is visa-required, and an Irish Residence Permit within 90 days of arrival. Everyone, regardless of nationality, needs a PPS number and must register the job in Revenue myAccount.',
    'Confirm nationality first - it decides whether this is a 12-week permit chain or nothing at all. For non-EEA hires the binding constraint is that the employment permit application must be RECEIVED at least 12 weeks before the intended start date; DETE''s processing queue is currently far shorter than that, so the 12-week rule, not the queue, sets the timeline. Ireland is not in the EU Blue Card scheme and not in the Schengen area.',
    'Critical Skills Employment Permit: salary threshold EUR 40,904 for occupations on the Critical Skills list, application fee EUR 1,000 with 90% refunded if refused. The General Employment Permit is the fallback route and carries a Labour Market Needs Test. DETE''s Trusted Partner Initiative is discontinued - employer verification moved into Employment Permits Online, and guides still advertising it as a fast-track are stale. A Critical Skills holder''s spouse receives Stamp 1G on registration and may work without their own permit, which the General Employment Permit does not offer.',
    '["Non-EEA: the employment permit application must be RECEIVED at least 12 weeks before the intended start date. This, not DETE processing time, is what sets the timeline.",
      "EU/EEA/Swiss nationals register NOTHING in Ireland - no permit, no visa, no residence card. Do not apply a generic arrival-registration deadline to them.",
      "Ireland is outside the Schengen area: a Spanish or other EU residence permit confers no right to enter Ireland. Visa-required nationals apply for a long-stay D visa at the Irish embassy in their country of residence.",
      "PPSN first, then Revenue registration, then the bank account. Each step issues the document the next one asks for, and an EEA citizen holds no IRP to use as proof of address.",
      "The employee - not the employer - must register the job in Revenue myAccount. Miss it and emergency tax reaches 40% plus USC from week 5.",
      "Non-EEA: IRP registration is within 90 days at Burgh Quay, Dublin, and costs EUR 300 - not the 7-14 days a generic European template would suggest.",
      "Ireland is NOT in the EU Blue Card scheme. Any Blue Card guidance for this destination is wrong."]',
    _now);

  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required, depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid()::text, _tid, 1, 'Nationality confirmed and immigration route chosen', 'hr', 1, NULL,
     'EU/EEA/Swiss: nothing to apply for. Any other nationality: an employment permit is needed before you travel.',
     'This single field decides between a 12-week permit chain and no immigration process at all. Confirm it before quoting any timeline.', 'ie_route_confirmed'),
    (gen_random_uuid()::text, _tid, 2, 'Signed employment contract (2 years for Critical Skills)', 'employer', 1, 1,
     'Required for the permit application and for your PPSN appointment.',
     'Critical Skills requires a 2-year contract and a salary at or above the EUR 40,904 threshold for listed occupations.', 'ie_offer_letter'),
    (gen_random_uuid()::text, _tid, 3, 'Valid passport (all travellers)', 'employee', 1, NULL,
     'Must cover the intended duration of stay.', NULL, 'ie_passport'),
    (gen_random_uuid()::text, _tid, 4, 'Employment permit submitted to DETE (non-EEA only)', 'employer', 0, 2,
     'Submitted through Employment Permits Online by your employer.',
     'Must be RECEIVED at least 12 weeks before the intended start date. Not applicable to EU/EEA/Swiss nationals.', 'ie_permit_submitted'),
    (gen_random_uuid()::text, _tid, 5, 'Employment permit granted (non-EEA only)', 'employee', 0, 4,
     'Check the permit conditions and start date before booking travel.',
     'Retain a copy for the HR file. Not applicable to EU/EEA/Swiss nationals.', 'ie_permit_granted'),
    (gen_random_uuid()::text, _tid, 6, 'Long-stay ''D'' visa obtained (visa-required nationals only)', 'employee', 0, 5,
     'Apply at the Irish embassy in your country of residence, not your country of citizenship. Ireland is outside Schengen, so an EU residence permit does not admit you.',
     'Sequenced AFTER the permit is granted. Not applicable to EU/EEA/Swiss or to non-visa-required nationalities.', 'ie_d_visa'),
    (gen_random_uuid()::text, _tid, 7, 'PPS number (PPSN) obtained', 'employee', 1, NULL,
     'Apply on MyWelfare.ie, then attend the mandatory in-person appointment. Bring photo ID, your signed offer and proof of Irish address under 3 months old. Allow 10-20 days.',
     'Applies to every nationality. Nothing downstream - payroll, tax, banking - can complete without it.', 'ie_ppsn'),
    (gen_random_uuid()::text, _tid, 8, 'Employment registered by the employee in Revenue myAccount', 'employee', 1, 7,
     'You must do this yourself; your employer cannot. Without it, emergency tax reaches 40% plus USC from week 5.',
     'Confirm before the first payroll run. This is the most common and most expensive miss for new arrivals.', 'ie_revenue_registration'),
    (gen_random_uuid()::text, _tid, 9, 'Irish Residence Permit (IRP) registered (non-EEA only)', 'employee', 0, NULL,
     'Within 90 days of arrival, at Burgh Quay in Dublin for a first registration. EUR 300. An employment-permit holder is normally granted Stamp 1.',
     'EU/EEA/Swiss nationals do NOT register and receive no IRP. A spouse of a Critical Skills holder receives Stamp 1G and may work without a permit.', 'ie_irp_registration'),
    (gen_random_uuid()::text, _tid, 10, 'Irish bank account opened', 'employee', 0, 8,
     'Banks want photo ID plus a separate proof of Irish address. An EEA citizen has no IRP to use, so Revenue correspondence is usually the first acceptable document.',
     'Required for salary payment. The PPSN and Revenue steps must come first.', 'ie_bank_account'),
    (gen_random_uuid()::text, _tid, 11, 'Housing secured and dependants planned', 'employee', 0, NULL,
     'Dublin lets move in days, not weeks. Have ID, proof of employment and references ready as one PDF.',
     'Confirm the relocation budget reflects Dublin rents. Dependants of a Critical Skills holder may join immediately.', 'ie_housing_dependants');

  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title, body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid()::text, _tid, 1, 'pre', 'Kickoff and route confirmation',
     'HR confirms whether your nationality requires an employment permit at all. EU/EEA/Swiss citizens can skip straight to the settle-in steps.',
     'Confirm nationality and choose the route. For non-EEA hires start the permit immediately - the 12-week receipt rule governs the start date.',
     'hr', 'T-16 weeks'),
    (gen_random_uuid()::text, _tid, 2, 'pre', 'Employment permit submitted (non-EEA)',
     'Your employer submits the permit application through Employment Permits Online.',
     'Must be received by DETE at least 12 weeks before the intended start date. Skip for EU/EEA/Swiss nationals.',
     'employer', 'T-12 weeks'),
    (gen_random_uuid()::text, _tid, 3, 'immigration', 'Permit granted, then visa if required',
     'Once the permit is granted, apply for a long-stay D visa at the Irish embassy where you live, if your nationality needs one.',
     'Sequence matters: permit first, visa second. Retain both for the compliance record.',
     'employee', 'T-6 to 8 weeks'),
    (gen_random_uuid()::text, _tid, 4, 'move', 'Arrival in Ireland',
     'No registration is required on arrival for EU/EEA/Swiss citizens. Other nationals should book their IRP appointment early - Burgh Quay slots go quickly.',
     'Confirm arrival. For non-EEA hires, track the 90-day IRP deadline from the date of entry.',
     'employee', 'T-0'),
    (gen_random_uuid()::text, _tid, 5, 'post', 'PPSN, Revenue and bank',
     'Apply for your PPSN on MyWelfare.ie, then register your job in Revenue myAccount, then open a bank account. That order is the only one that completes.',
     'Confirm the Revenue registration before the first payroll run to avoid emergency tax at 40% plus USC.',
     'employee', 'T+1 to 3 weeks'),
    (gen_random_uuid()::text, _tid, 6, 'post', 'Settle-in complete',
     'Non-EEA nationals: complete IRP registration within 90 days. Everyone: register with a GP, and confirm health cover.',
     'Confirm IRP is registered where applicable and the tax position is correct. Schedule a 3-month check-in.',
     'hr', 'T+4 to 12 weeks');

  RAISE NOTICE 'IE readiness template inserted with id %', _tid;
END $$;
