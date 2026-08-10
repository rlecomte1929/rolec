-- [AIQ-1795] RESID-PERMIT-DE must not attach to an EEA free-movement case.
--
-- The defect: its single trigger rule declares conditions {"destination_country": "DE"} and no
-- visa_type. trigger_engine._matches_conditions only checks the keys a rule DECLARES, so the rule
-- matched every DE-destination case — including FR→DE, where trigger_engine._build_context
-- resolves visa_type 'eea_registration' because both countries are in _EEA_COUNTRIES.
--
-- Why that is not a cosmetic over-match. The template is "Residence permit appointment
-- (Auslaenderbehoerde)" and its 5 fields are a full appointment package: passport ORIGINAL,
-- Anmeldung reference, biometric photo. Attaching it tells an EU citizen to collect a document
-- German law does not issue them:
--
--   FreizuegG/EU § 2(4), official English translation:
--     "EU citizens shall not require a visa in order to enter the federal territory or a
--      residence title in order to stay in the federal territory."
--   https://www.gesetze-im-internet.de/englisch_freiz_gg_eu/englisch_freiz_gg_eu.html
--
-- Current § 5 issues only a residence card to NON-EU family members (§5(1)) and a
-- permanent-residence certificate on application (§5(5)). The old Freizuegigkeitsbescheinigung
-- was abolished — there is no ordinary residence document for an EU citizen to collect.
--
-- GATED, NOT RETIRED. For a THIRD-COUNTRY national arriving in Germany the eAT-collection
-- appointment is a real obligation, and this is the only template covering it. The field roster
-- is generically right for that audience (identity document, biometric photo, proof of
-- registration, arrival date), and the seed's own header already calls these "starter field
-- rosters ... draft until ops/legal review" — which is what verification_status='representative'
-- means. Deleting real coverage to fix an over-match would be the worse error.
--
-- FOUR RULES, ONE PER NON-EEA visa_type. _matches_conditions compares scalars with
-- case-insensitive equality and has no list/IN support, so "any non-EEA visa_type" cannot be one
-- condition. But trigger_rules IS iterated as an array (trigger_engine.py, `for rule in
-- trigger_rules` at lines 129 and 493), so one rule per value expresses it. The four values are
-- the complete output of _purpose_to_visa_type; anything else — including a NULL visa_type from
-- an unknown purpose — fails closed at `if actual is None: return False`.
--
-- Deliberately NOT touched:
--   * BLUE-CARD and WORK-VISA-DE already declare visa_type 'skilled_worker', which
--     _build_context can never produce on an EEA corridor. They look wrong and are right.
--   * ANMELDUNG is ungated and correct — § 17 BMG applies to everyone moving into a German
--     dwelling, regardless of nationality. Gating it would drop the one real German arrival
--     obligation.
--
-- Forward migration: 20260610010000 is already applied and is not edited in place.
-- Idempotent: sets the full array by code, so re-running converges.

UPDATE public.form_templates
SET trigger_rules = jsonb_build_array(
      jsonb_build_object(
        'event', 'roadmap.arrival_confirmed',
        'priority', 50,
        'conditions', jsonb_build_object('destination_country', 'DE', 'visa_type', 'skilled_worker'),
        'for_persons', jsonb_build_array('employee'),
        'blocked_by_template_code', NULL
      ),
      jsonb_build_object(
        'event', 'roadmap.arrival_confirmed',
        'priority', 50,
        'conditions', jsonb_build_object('destination_country', 'DE', 'visa_type', 'intra_company_transfer'),
        'for_persons', jsonb_build_array('employee'),
        'blocked_by_template_code', NULL
      ),
      jsonb_build_object(
        'event', 'roadmap.arrival_confirmed',
        'priority', 50,
        'conditions', jsonb_build_object('destination_country', 'DE', 'visa_type', 'family_join'),
        'for_persons', jsonb_build_array('employee'),
        'blocked_by_template_code', NULL
      ),
      jsonb_build_object(
        'event', 'roadmap.arrival_confirmed',
        'priority', 50,
        'conditions', jsonb_build_object('destination_country', 'DE', 'visa_type', 'remote_work'),
        'for_persons', jsonb_build_array('employee'),
        'blocked_by_template_code', NULL
      )
    ),
    updated_at = now()
WHERE code = 'RESID-PERMIT-DE';

COMMENT ON COLUMN public.form_templates.trigger_rules IS
  'Array of attach rules. Each rule''s `conditions` keys MUST be members of what trigger_engine._build_context returns (case_uuid, employee_id, destination_country, origin_country, visa_type, has_spouse, has_children) — _matches_conditions fails closed on an unknown key, so an invented key makes a template silently unattachable. Equally, an OMITTED key is never checked: leaving visa_type out of a permit template matched EEA free-movers (AIQ-1795). Express "any of N values" as N rules; there is no list support.';
