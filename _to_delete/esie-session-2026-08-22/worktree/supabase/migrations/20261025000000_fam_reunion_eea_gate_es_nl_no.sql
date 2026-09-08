-- [AIQ-1795c] Family-reunification templates for ES, NL and NO must not attach to
-- EEA free-movers.
--
-- The same defect as AIQ-1795 (RESID-PERMIT-DE) and AIQ-1795b (FAM-SPOUSE/FAM-CHILD),
-- in six more templates that the first two passes missed:
--
--   ES-FAM-SPOUSE  ES-FAM-CHILD   Family reunification - spouse / child (Reagrupacion)
--   NL-FAM-SPOUSE  NL-FAM-CHILD   Family reunification - partner / child
--   UTL-2011F      UTL-2011B      Soeknad om familieinnvandring (ektefelle / barn)
--
-- Each carried a single rule conditioned on destination_country alone. `_matches_conditions`
-- only checks the keys a rule DECLARES, so an omitted visa_type is never compared and the
-- rule matched every case for that destination -- including visa_type = 'eea_registration',
-- which `_build_context` produces whenever origin AND destination are both EEA. ES, NL and
-- NO are all EEA. So an EU citizen moving to Spain with a spouse was told to file a
-- family-reunification application they have a treaty right not to need.
--
-- Why these six were missed twice. AIQ-1795b shipped a CI guard for exactly this class, but
-- its permit-like classifier keyed off a name regex plus category 'work_permit'. The German
-- templates are named "Family reunion VISA - spouse (FAMILIENNACHZUG)" and matched two
-- tokens by coincidence; "Family reunification - spouse" and "Soeknad om familieinnvandring"
-- match none, and all six are category 'family'. The guard exited 0 on a tree containing
-- every one of them. `scripts/check_form_template_honesty.py` is widened in the same commit
-- so it now fails on this file's pre-state.
--
-- The visa_type list is exhaustive, not a judgement call. `_purpose_to_visa_type` maps
-- exactly four purposes -- work -> skilled_worker, intra_company_transfer, family_join,
-- remote_work -- and `eea_registration` is the only other value `_build_context` can return.
-- One rule per non-EEA visa_type is therefore the complete complement of the EEA case;
-- `_matches_conditions` has no list support, so N values means N rules.
--
-- Known and accepted: a case whose purpose maps to NULL (unset or unrecognised) on a
-- non-EEA corridor now matches no rule and gets no family template. That is fail-closed --
-- silence rather than a false requirement -- and is the same trade AIQ-1795/1795b already
-- made. Correct behaviour is to fix the purpose, not to re-open the gate.
--
-- Rewrites each existing rule in place rather than restating it, so event, priority
-- (ES/NL 85/84, NO 90) and for_persons are carried across verbatim and cannot be
-- mis-transcribed. Idempotent via the NOT (? 'visa_type') guard: re-running is a no-op
-- because every rule carries visa_type afterwards.

UPDATE public.form_templates t
SET trigger_rules = (
      SELECT jsonb_agg(
               elem.r || jsonb_build_object(
                 'conditions', (elem.r -> 'conditions')
                               || jsonb_build_object('visa_type', vt)
               )
             )
      FROM jsonb_array_elements(t.trigger_rules) AS elem(r),
           unnest(ARRAY['skilled_worker', 'intra_company_transfer',
                        'family_join', 'remote_work']) AS vt
    ),
    updated_at = now()
WHERE t.code IN ('ES-FAM-SPOUSE', 'ES-FAM-CHILD',
                 'NL-FAM-SPOUSE', 'NL-FAM-CHILD',
                 'UTL-2011F', 'UTL-2011B')
  AND jsonb_typeof(t.trigger_rules) = 'array'
  AND EXISTS (
        SELECT 1 FROM jsonb_array_elements(t.trigger_rules) AS e(r)
        WHERE NOT (e.r -> 'conditions' ? 'visa_type')
      );

-- Fail loudly rather than reporting success on a partial write.
DO $$
DECLARE ungated int;
BEGIN
  SELECT count(*) INTO ungated
  FROM public.form_templates t
  WHERE t.code IN ('ES-FAM-SPOUSE', 'ES-FAM-CHILD',
                   'NL-FAM-SPOUSE', 'NL-FAM-CHILD',
                   'UTL-2011F', 'UTL-2011B')
    AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(t.trigger_rules) AS e(r)
          WHERE NOT (e.r -> 'conditions' ? 'visa_type')
        );
  IF ungated > 0 THEN
    RAISE EXCEPTION
      '[AIQ-1795c] % template(s) still carry an ungated rule after the update', ungated;
  END IF;
END $$;
