-- Persist wizard progress per assignment so the employee hub can show
-- "Intake form: N / TOTAL steps" instead of a coarse Submitted/Not-submitted
-- badge derived from assignment.status.
--
-- Notes:
--   * We only persist the *step counter*, not the wizard form data itself.
--     Form data continues to live in component state until final submit (the
--     existing patchCase call at wizard completion). When per-step draft
--     persistence is built, it should write to the same row.
--   * No new table is introduced — RLS policies already cover case_assignments
--     row scope, so the new columns inherit existing tenant scoping.
--   * Defaults are conservative: 0 = "not started", 7 matches today's
--     STEP_LABELS constant in EmployeeIntakePage. Bumping STEP_LABELS in the
--     frontend should be paired with a follow-up migration changing the
--     default; existing rows can stay on 7 since callers pass total_steps
--     explicitly on every update.

ALTER TABLE IF EXISTS public.case_assignments
  ADD COLUMN IF NOT EXISTS intake_step smallint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS intake_total_steps smallint NOT NULL DEFAULT 7,
  ADD COLUMN IF NOT EXISTS intake_updated_at timestamptz NULL;

-- Sanity constraint: step must fit within total_steps and be non-negative.
-- Total_steps must be > 0 to avoid divide-by-zero on the frontend percentage
-- calc (when we add one).
ALTER TABLE IF EXISTS public.case_assignments
  DROP CONSTRAINT IF EXISTS case_assignments_intake_progress_bounds;

ALTER TABLE IF EXISTS public.case_assignments
  ADD CONSTRAINT case_assignments_intake_progress_bounds
  CHECK (
    intake_step >= 0
    AND intake_total_steps > 0
    AND intake_step <= intake_total_steps
  );
