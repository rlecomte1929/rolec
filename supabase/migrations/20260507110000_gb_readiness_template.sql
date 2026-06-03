-- ============================================================
-- Sprint F: Add GB (UK Skilled Worker) readiness template
-- ============================================================
-- Inserts the GB template and its child rows if they do not
-- already exist (idempotent via ON CONFLICT DO NOTHING).
-- ============================================================

DO $$
DECLARE
  _tid UUID := gen_random_uuid();
  _dest TEXT := 'GB';
  _route TEXT := 'employment';
  _now TIMESTAMPTZ := NOW();
  _existing UUID;
BEGIN

  -- Skip if already present
  SELECT id INTO _existing
    FROM readiness_templates
   WHERE destination_key = _dest AND route_key = _route
   LIMIT 1;

  IF _existing IS NOT NULL THEN
    RAISE NOTICE 'GB readiness template already exists – skipping.';
    RETURN;
  END IF;

  -- ── Template ─────────────────────────────────────────────
  INSERT INTO readiness_templates
    (id, destination_key, route_key, route_title,
     employee_summary, hr_summary, internal_notes_hr,
     watchouts_json, updated_at)
  VALUES
    (_tid, _dest, _route,
     'United Kingdom — Skilled Worker visa (sponsored route)',
     'Your employer holds a sponsor licence and will assign you a Certificate of Sponsorship (CoS). You then apply for a Skilled Worker visa before travelling to the UK. ReloPass tracks each step so nothing slips.',
     'Confirm sponsor licence is active, assign an undefined or defined CoS as appropriate, and support the employee''s visa application. Right-to-work check on Day 1 is mandatory.',
     'Check CoS assignment lead time (defined CoS needs Home Office approval, ~5 business days). Ensure salary meets minimum threshold for role SOC code. BRP collection from Post Office within 10 days of arrival.',
     '["CoS must be assigned before the employee submits their visa application — allow at least 1 week buffer.",
       "Salary must meet both the general threshold and the specific SOC code going rate; verify before issuing CoS.",
       "BRP card is sent to a UK address — employee must collect within 10 days of arrival.",
       "Right-to-work check must be completed on or before Day 1; share code expires in 90 days."]',
     _now
    );

  -- ── Checklist items ───────────────────────────────────────
  INSERT INTO readiness_template_checklist_items
    (id, template_id, sort_order, title, owner_role, required,
     depends_on_sort_order, notes_employee, notes_hr, stable_key)
  VALUES
    (gen_random_uuid(), _tid, 1,
     'Formal offer letter confirming role, salary & SOC code',
     'employer', 1, NULL,
     'Required for CoS assignment and visa application.',
     'Salary must satisfy both general threshold and going rate for the SOC code.',
     'gb_sw_offer_letter'),

    (gen_random_uuid(), _tid, 2,
     'Certificate of Sponsorship (CoS) assigned',
     'hr', 1, NULL,
     'You will need the CoS reference number to apply for your visa.',
     'Use undefined CoS for most new hires; defined CoS if employee is already in UK on another route.',
     'gb_sw_cos_assigned'),

    (gen_random_uuid(), _tid, 3,
     'Valid passport (all travellers)',
     'employee', 1, NULL,
     'Must be valid for the duration of your intended stay.',
     NULL,
     'gb_sw_passport'),

    (gen_random_uuid(), _tid, 4,
     'English language evidence',
     'employee', 1, NULL,
     'Degree taught in English, or approved test (IELTS/LanguageCert). Check UKVI approved providers.',
     'Exempt if national of majority English-speaking country.',
     'gb_sw_english_evidence'),

    (gen_random_uuid(), _tid, 5,
     'Maintenance funds evidence (if not covered by employer)',
     'employee', 0, NULL,
     '£1,270 in bank for 28 consecutive days unless employer certifies maintenance.',
     'Certify maintenance on CoS to remove this requirement for the employee.',
     'gb_sw_finance_evidence'),

    (gen_random_uuid(), _tid, 6,
     'Online visa application submitted & biometrics booked',
     'employee', 1, 2,
     'Apply at least 3 months before start date. Biometrics at UKVCAS service point.',
     'Provide IHS surcharge payment confirmation number if employer covers it.',
     'gb_sw_visa_application'),

    (gen_random_uuid(), _tid, 7,
     'Skilled Worker visa granted',
     'employee', 1, 6,
     'Check vignette dates — first entry must be on or before the valid from date.',
     'Retain copy for sponsor compliance file.',
     'gb_sw_visa_granted'),

    (gen_random_uuid(), _tid, 8,
     'Right-to-work check completed (Day 1)',
     'hr', 1, 7,
     'Use the UKVI online share code to allow HR to verify.',
     'Statutory excuse requires online check for visa nationals — record date and outcome.',
     'gb_sw_rtw_check'),

    (gen_random_uuid(), _tid, 9,
     'BRP card collected from Post Office',
     'employee', 1, 7,
     'Collect within 10 days of arrival. Address on visa letter shows which Post Office branch.',
     'Retain copy for compliance file; chase if not confirmed collected.',
     'gb_sw_brp_collection'),

    (gen_random_uuid(), _tid, 10,
     'Housing & schooling shortlist (if family)',
     'employee', 0, NULL,
     'Dependant visas can be applied at the same time.',
     'Confirm whether employer covers relocation costs.',
     'gb_sw_housing_school');

  -- ── Milestones ────────────────────────────────────────────
  INSERT INTO readiness_template_milestones
    (id, template_id, sort_order, phase, title,
     body_employee, body_hr, owner_role, relative_timing)
  VALUES
    (gen_random_uuid(), _tid, 1, 'pre',
     'Kickoff & sponsorship check',
     'HR confirms your employer is a licensed sponsor and outlines the Skilled Worker timeline.',
     'Verify sponsor licence is active, check CoS allocation, confirm salary vs SOC code thresholds.',
     'hr', 'T-12 weeks'),

    (gen_random_uuid(), _tid, 2, 'pre',
     'CoS assigned',
     'You receive your CoS reference number — keep it safe for the visa application.',
     'Assign CoS via sponsor management system; note expiry (3 months from assignment).',
     'hr', 'T-10 weeks'),

    (gen_random_uuid(), _tid, 3, 'pre',
     'Document pack ready',
     'Gather passport, English evidence, finances (if needed), and any dependant documents.',
     'Review pack for completeness before employee submits application.',
     'employee', 'T-9 weeks'),

    (gen_random_uuid(), _tid, 4, 'immigration',
     'Visa application submitted & biometrics',
     'Submit online, pay IHS surcharge, attend biometrics appointment.',
     'Confirm IHS paid (or reimbursed per policy); track application reference.',
     'employee', 'T-8 weeks'),

    (gen_random_uuid(), _tid, 5, 'immigration',
     'Visa decision received',
     'Check vignette validity. First entry before ''valid from'' date.',
     'File decision copy; update compliance record.',
     'hr', 'T-4 weeks'),

    (gen_random_uuid(), _tid, 6, 'move',
     'Arrival in UK & right-to-work check',
     'Generate share code; HR will complete the online check on Day 1.',
     'Complete UKVI online right-to-work check on or before start date.',
     'hr', 'T-0'),

    (gen_random_uuid(), _tid, 7, 'post',
     'BRP collected & settle-in',
     'Collect BRP within 10 days. Start bank account, NI number, GP registration.',
     'Confirm BRP collected; file copy; schedule 6-month compliance check.',
     'employee', 'T+1 to 2 weeks');

  RAISE NOTICE 'GB readiness template inserted with id %', _tid;

END $$;
