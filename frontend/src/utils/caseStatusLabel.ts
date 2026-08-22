/**
 * TASK-005 / AIQ-1044 — single source of truth for case status display labels.
 *
 * The same case was showing different status text depending on the page: the
 * Cases list (HrDashboard) mapped statuses to friendly labels while the Mobility
 * center rendered the raw enum (`assigned`, `awaiting intake`). Both surfaces now
 * call this, so a case reads identically everywhere.
 *
 * Note `awaiting_intake` IS the "Intake in progress" state — there is no separate
 * INTAKE_IN_PROGRESS enum value (see AssignmentStatus in types.ts). `created` and
 * `assigned` are both the "Not started" state; `assigned` is never shown raw.
 *
 * Unknown / richer pipeline statuses the Mobility center may carry (e.g.
 * `discovery`, `housing`, `visa_submitted`, `done`) fall back to a humanised form
 * rather than being flattened, preserving their meaning.
 */
const CASE_STATUS_LABELS: Record<string, string> = {
  created: 'Not started',
  assigned: 'Not started',
  awaiting_intake: 'Intake in progress',
  submitted: 'Awaiting HR review',
  // [AIQ-2088] `approved` used to read 'Complete' and `closed` 'Canceled'. Both were
  // wrong about the lifecycle: `approved` is granted when HR reviews the employee's
  // SUBMITTED INTAKE (the `assignment.approved` event) — weeks before anyone moves —
  // so calling it Complete told HR a relocation had finished when it had barely
  // started. `closed` is the terminal state, and it covers a move that finished as
  // well as one that was abandoned; 'Canceled' asserted the second.
  approved: 'Approved',
  rejected: 'Rejected',
  closed: 'Closed',
};

export function getCaseStatusLabel(status: string | null | undefined): string {
  if (!status) return '—';
  const key = status.toLowerCase();
  return CASE_STATUS_LABELS[key] ?? status.replace(/_/g, ' ');
}
