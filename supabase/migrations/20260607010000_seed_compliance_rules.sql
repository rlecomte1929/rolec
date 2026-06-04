-- ============================================================================
-- BL-Compliance.2 (AIQ-744) · seed the launch compliance rule set
--
-- Inserts the 3 launch rules into public.compliance_rules (created by
-- BL-Compliance.1 / 20260607000000). Each rule's trigger_condition is a
-- self-describing JSON document that the BL-Compliance.3 evaluator consumes:
--
--   {
--     "type":     "date_threshold" | "day_count" | "missing_field",
--     "field":    "<case/profile field the evaluator reads>",
--     "operator": "within_days" | "gte" | "lte" | "is_null",
--     "value":    <number | null>,
--     "unit":     "days"            -- present for date_threshold / day_count
--   }
--
-- Deterministic UUIDs + ON CONFLICT (id) DO NOTHING make this seed replay-safe.
-- ============================================================================

begin;

insert into public.compliance_rules (id, category, severity, description, trigger_condition)
values
  (
    'c0119a01-0000-4000-8000-000000000001',
    'immigration',
    'high',
    'Residence or work permit is approaching its expiry date.',
    '{"type":"date_threshold","field":"permit_expiry_date","operator":"within_days","value":60,"unit":"days"}'::jsonb
  ),
  (
    'c0119a02-0000-4000-8000-000000000002',
    'tax',
    'high',
    'Employee is approaching the 183-day presence threshold for host-country tax residency.',
    '{"type":"day_count","field":"days_present_in_host","operator":"gte","value":183,"unit":"days"}'::jsonb
  ),
  (
    'c0119a03-0000-4000-8000-000000000003',
    'employer',
    'high',
    'Employer registration for the host country has not been recorded for this case.',
    '{"type":"missing_field","field":"employer_registration_id","operator":"is_null","value":null}'::jsonb
  )
on conflict (id) do nothing;

commit;

-- ============================================================================
-- Rollback (manual):
--   delete from public.compliance_rules
--    where id in (
--      'c0119a01-0000-4000-8000-000000000001',
--      'c0119a02-0000-4000-8000-000000000002',
--      'c0119a03-0000-4000-8000-000000000003'
--    );
-- ============================================================================
