// Canonical employee-intake step definitions — the single source of truth for
// how many steps the intake wizard has. The wizard (EmployeeIntakePage) renders
// these labels and is the only writer of `intake_step`; the dashboard
// (EmployeeJourney / JourneySpine) must derive the *total* from here too, so the
// two surfaces never disagree (e.g. dashboard "Step 1 of 7" vs wizard "Step 1 / 6").
//
// Do NOT trust `case_assignments.intake_total_steps` from the API for the total:
// historical rows store a stale 7 while the wizard has 6 steps. This constant is
// authoritative.
export const INTAKE_STEP_LABELS = [
  'Journey',
  'About You',
  'My People',
  'Work & Place',
  'My Needs',
  'Review',
] as const;

export const INTAKE_TOTAL_STEPS = INTAKE_STEP_LABELS.length;
