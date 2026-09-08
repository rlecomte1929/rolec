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
  approved: 'Complete',
  rejected: 'Rejected',
  closed: 'Canceled',
};

export function getCaseStatusLabel(status: string | null | undefined): string {
  if (!status) return '—';
  const key = status.toLowerCase();
  return CASE_STATUS_LABELS[key] ?? status.replace(/_/g, ' ');
}
