-- [AIQ-1795b] FAM-SPOUSE and FAM-CHILD must not attach to EEA free-movement cases.
--
-- The same defect 20261023000000 fixed for RESID-PERMIT-DE, in two more templates. Both
-- declare {"destination_country": "DE"} plus a family flag and NO visa_type, and
-- _matches_conditions only checks the keys a rule DECLARES — so both match every
-- DE-destination case, including FR->DE where _build_context resolves
-- visa_type 'eea_registration'.
--
-- Why it is wrong: "Familiennachzug" (family reunion visa) is a THIRD-COUNTRY-NATIONAL
-- procedure. A family member of an EU citizen exercising free movement holds DERIVED
-- free-movement rights and needs no such visa:
--
--   FreizuegG/EU § 3 grants the right of residence to dependants of an EU citizen
--   entitled to freedom of movement. § 2(4): "EU citizens shall not require a visa in
--   order to enter the federal territory or a residence title in order to stay in the
--   federal territory."
--   https://www.gesetze-im-internet.de/englisch_freiz_gg_eu/englisch_freiz_gg_eu.html
--
-- These are worse than the one already fixed in one respect: they fire on
-- roadmap.profile_completed, i.e. EARLIER in the journey, so the employee meets the wrong
-- instruction sooner.
--
-- GATED, NOT RETIRED, on the same reasoning as 20261023000000: for a third-country
-- national relocating to Germany with family, Familiennachzug is a real procedure and
-- these are the only templates covering it. Gating preserves that coverage; retiring
-- would delete it.
--
-- FOUR RULES EACH, one per non-EEA visa_type — the complete output of
-- trigger_engine._purpose_to_visa_type. _matches_conditions compares scalars and has no
-- list support, but trigger_rules IS iterated as an array (trigger_engine.py:129, :493).
-- An unknown purpose yields visa_type None and fails closed at
-- `if actual is None: return False`.
--
-- for_persons and the family flag are preserved per template: FAM-SPOUSE stays
-- ['spouse'] + has_spouse, FAM-CHILD stays ['each_child'] + has_children. Changing those
-- would alter WHO the form is instantiated for, which is not what this fixes.
--
-- Found by scripts/check_form_template_honesty.py, added in the same change. That script
-- is the actual deliverable here: RESID-PERMIT-DE was fixed by hand and these two were
-- sitting beside it, so the class needed to become machine-detectable rather than the
-- instances being found one at a time.
--
-- Forward migration; 20260610010000 is already applied and is not edited in place.
-- Idempotent: sets the full array by code, so re-running converges.

-- Written as two explicit UPDATEs with LITERAL codes rather than a loop over a VALUES
-- list. The loop version worked but used `WHERE code = t.code`, and
-- scripts/check_form_template_honesty.py detects "this seeded rule was rewritten later"
-- by looking for a literal `WHERE ... code = '<CODE>'`. A variable there made the fix
-- invisible to the guard, which then kept reporting these two as violations forever.
-- Clever SQL that defeats the checker reading it is not worth two saved lines.

UPDATE public.form_templates
SET trigger_rules = (
      SELECT jsonb_agg(
               jsonb_build_object(
                 'event', 'roadmap.profile_completed',
                 'priority', 85,
                 'conditions', jsonb_build_object(
                   'destination_country', 'DE',
                   'visa_type', vt,
                   'has_spouse', true
                 ),
                 'for_persons', jsonb_build_array('spouse'),
                 'blocked_by_template_code', NULL
               )
             )
      FROM unnest(ARRAY['skilled_worker', 'intra_company_transfer',
                        'family_join', 'remote_work']) AS vt
    ),
    updated_at = now()
WHERE code = 'FAM-SPOUSE';

UPDATE public.form_templates
SET trigger_rules = (
      SELECT jsonb_agg(
               jsonb_build_object(
                 'event', 'roadmap.profile_completed',
                 'priority', 84,
                 'conditions', jsonb_build_object(
                   'destination_country', 'DE',
                   'visa_type', vt,
                   'has_children', true
                 ),
                 'for_persons', jsonb_build_array('each_child'),
                 'blocked_by_template_code', NULL
               )
             )
      FROM unnest(ARRAY['skilled_worker', 'intra_company_transfer',
                        'family_join', 'remote_work']) AS vt
    ),
    updated_at = now()
WHERE code = 'FAM-CHILD';
