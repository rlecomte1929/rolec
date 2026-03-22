import type { EmployeeLinkedOverviewRow } from '../types/employeeAssignmentOverview';

/** True when employee assignment overview should load (not only under `/employee/*`). */
export function shouldLoadEmployeeAssignmentOverview(pathname: string): boolean {
  return (
    pathname.startsWith('/employee') ||
    pathname.startsWith('/services') ||
    pathname.startsWith('/quotes') ||
    pathname.startsWith('/resources') ||
    pathname.startsWith('/providers') ||
    pathname.startsWith('/messages') ||
    pathname.startsWith('/hr/policy') ||
    pathname.startsWith('/employee/hr-policy')
  );
}

export function parseAssignmentSearchParam(search: string): string | null {
  const q = search.startsWith('?') ? search.slice(1) : search;
  const v = (new URLSearchParams(q).get('assignment') || '').trim();
  return v || null;
}

/**
 * Pick which linked assignment drives employee flows that need a single id.
 * - 0–1 linked: use primary from overview (or optional ?assignment= if valid).
 * - 2+ linked: require ?assignment= that matches a linked row, else needsPicker.
 */
export function resolveScopedAssignmentId(input: {
  linkedCount: number;
  linkedSummaries: EmployeeLinkedOverviewRow[];
  primaryAssignmentId: string | null;
  queryAssignmentId: string | null;
}): { effectiveId: string | null; needsPicker: boolean } {
  const { linkedCount, linkedSummaries, primaryAssignmentId, queryAssignmentId } = input;
  const allowed = new Set(
    linkedSummaries.map((r) => r.assignment_id).filter((x): x is string => Boolean(x))
  );

  if (linkedCount <= 1) {
    if (queryAssignmentId && allowed.has(queryAssignmentId)) {
      return { effectiveId: queryAssignmentId, needsPicker: false };
    }
    return { effectiveId: primaryAssignmentId, needsPicker: false };
  }

  if (queryAssignmentId && allowed.has(queryAssignmentId)) {
    return { effectiveId: queryAssignmentId, needsPicker: false };
  }
  return { effectiveId: null, needsPicker: true };
}

/** Append or replace `assignment` query param (keeps other params). */
export function withAssignmentQuery(path: string, assignmentId: string): string {
  const [base, existing] = path.split('?');
  const p = new URLSearchParams(existing || '');
  p.set('assignment', assignmentId);
  return `${base}?${p.toString()}`;
}
