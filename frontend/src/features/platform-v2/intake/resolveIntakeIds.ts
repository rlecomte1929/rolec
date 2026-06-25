import type { EmployeeLinkedOverviewRow } from '../../../types/employeeAssignmentOverview';

export interface ResolvedIntakeIds {
  /** The canonical assignment_id to fetch the draft / autosave with (null until resolved). */
  assignmentId: string | null;
  /** The canonical case_id for the submit's PATCH /api/cases/{caseId} (null when no param). */
  caseId: string | null;
}

/**
 * The intake route param (`:caseId`) may carry EITHER a `case_id` (sidebar
 * "Intake form" tab) or an `assignment_id` (dashboard "Continue intake" button).
 * Resolve it against the employee's linked assignments to the canonical
 * `assignment_id` (drives GET /api/employee/assignments/{id}/intake hydration +
 * autosave) and `case_id` (drives the submit's PATCH /api/cases/{caseId}).
 *
 * Matching by `assignment_id` first, then `case_id`, lets BOTH entry points run
 * the identical loader. `caseId` falls back to the param itself for HR deep-links
 * that carry a case UUID not yet present in `linkedSummaries`.
 */
export function resolveIntakeIds(
  param: string | undefined | null,
  linkedSummaries: ReadonlyArray<
    Pick<EmployeeLinkedOverviewRow, 'assignment_id' | 'case_id'>
  >,
): ResolvedIntakeIds {
  if (!param) return { assignmentId: null, caseId: null };
  const row =
    linkedSummaries.find((r) => r.assignment_id === param) ??
    linkedSummaries.find((r) => r.case_id === param);
  return {
    assignmentId: row?.assignment_id ?? null,
    caseId: row?.case_id ?? param,
  };
}
