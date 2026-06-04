-- ============================================================================
-- BL-Compliance follow-up · Phase A3 — add precondition to missing_employer_reg
--
-- Without a precondition, the missing_field rule for employer_reg_number fires
-- on every relocation_case whose imm_employee_profiles row is absent — i.e.
-- ~all open prod cases on first run. Adding precondition_field=profile_exists
-- restricts firing to cases where intake has started but the field wasn't
-- filled. The evaluator (backend/app/services/compliance_evaluator.py) consumes
-- this key.
--
-- Replay-safe: jsonb_set on the existing row by deterministic id.
-- ============================================================================

begin;

update public.compliance_rules
   set trigger_condition = jsonb_set(
         trigger_condition,
         '{precondition_field}',
         '"profile_exists"'::jsonb,
         true
       ),
       updated_at = now()
 where id = 'c0119a03-0000-4000-8000-000000000003';

commit;

-- ============================================================================
-- Rollback (manual):
--   update public.compliance_rules
--      set trigger_condition = trigger_condition - 'precondition_field'
--    where id = 'c0119a03-0000-4000-8000-000000000003';
-- ============================================================================
