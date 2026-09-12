/**
 * Zero-count claims on the employee dashboard must be gated on the overview
 * having actually resolved.
 *
 * "No case is linked yet" / the manual-claim onboarding are derived from
 * `linkedCount === 0 && pendingCount === 0`. Those counts are also 0 in two
 * states where we know nothing:
 *
 *   1. the overview request failed  (`overviewError` is set), and
 *   2. the overview returned HTTP 200 with `overview_degraded: true` — the
 *      backend swallows a build failure into an empty payload
 *      (backend/main.py get_employee_assignments_overview).
 *
 * In both, telling a relocating employee their case does not exist is a false
 * statement, not an empty state. Resolve the render flags here so the rule lives
 * in one place instead of in each JSX guard.
 */

export const OVERVIEW_DEGRADED_MESSAGE =
  'We could not load your assignments just now. Nothing has changed on your cases — try again in a moment.';

export type OverviewResolution = {
  /** No trustworthy answer: the request failed, or the payload came back degraded. */
  unresolved: boolean;
  /** Render the manual-claim onboarding — only when we know the employee has nothing. */
  showManualClaim: boolean;
  /** Render the assignment-status and active-cases sections. */
  showAssignmentSections: boolean;
};

export function resolveOverviewState(input: {
  overviewError?: string | null;
  overviewDegraded?: boolean;
  linkedCount: number;
  pendingCount: number;
}): OverviewResolution {
  const unresolved = Boolean(input.overviewError) || Boolean(input.overviewDegraded);
  const hasLinked = input.linkedCount > 0;
  const hasPendingOnly = !hasLinked && input.pendingCount > 0;
  return {
    unresolved,
    showManualClaim: !unresolved && !hasLinked && !hasPendingOnly,
    // Rows we actually received are still worth showing; the banner explains the rest.
    showAssignmentSections: hasLinked || hasPendingOnly,
  };
}
