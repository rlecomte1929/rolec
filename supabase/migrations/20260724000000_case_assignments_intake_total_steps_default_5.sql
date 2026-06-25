-- Reconcile intake_total_steps with the canonical 5-step v2 intake wizard.
-- The original migration (20260529130000_case_assignments_intake_progress.sql) set a
-- DEFAULT of 7, so fresh assignments reported intakeTotalSteps:7 while the UI renders
-- 5 tabs ("Step X of 5"). The frontend already ignores the stale stored value, but
-- this aligns the stored/served number so the API and UI agree.
-- Idempotent: re-running is a no-op.

ALTER TABLE public.case_assignments
  ALTER COLUMN intake_total_steps SET DEFAULT 5;

UPDATE public.case_assignments
  SET intake_total_steps = 5
  WHERE intake_total_steps = 7;
