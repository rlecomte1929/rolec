import type { EmployeeLinkedOverviewRow } from '../types/employeeAssignmentOverview';
import { getAuthItem } from './demo';

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

/** Collapse duplicate overview rows (same assignment_id) so UI / picker logic stay consistent. */
export function dedupeLinkedSummariesByAssignmentId(
  rows: EmployeeLinkedOverviewRow[]
): EmployeeLinkedOverviewRow[] {
  const m = new Map<string, EmployeeLinkedOverviewRow>();
  for (const r of rows) {
    const id = (r.assignment_id || '').trim();
    if (id && !m.has(id)) m.set(id, r);
  }
  return [...m.values()];
}

function preferredAssignmentStorageKey(): string {
  const uid = getAuthItem('relopass_user_id') || 'anon';
  return `relopass_employee_preferred_assignment_${uid}`;
}

/**
 * Last assignment the employee focused (wizard, case summary, or explicit picker).
 * Cleared with other `relopass_*` keys on logout via clearAuthItems.
 */
export function getPreferredEmployeeAssignmentId(): string | null {
  const v = localStorage.getItem(preferredAssignmentStorageKey())?.trim();
  return v || null;
}

export function setPreferredEmployeeAssignmentId(assignmentId: string): void {
  const id = assignmentId.trim();
  if (!id) return;
  localStorage.setItem(preferredAssignmentStorageKey(), id);
}

/**
 * Pick which linked assignment drives employee flows that need a single id.
 * - `?assignment=` wins if it matches a linked row.
 * - Else stored preference (wizard / case URL / prior picker choice) if it still matches.
 * - 0–1 linked after dedupe: primary, no picker.
 * - 2+ distinct linked and no valid query or preference: needsPicker.
 */
export function resolveScopedAssignmentId(input: {
  linkedSummaries: EmployeeLinkedOverviewRow[];
  primaryAssignmentId: string | null;
  queryAssignmentId: string | null;
  /** Pass null to skip reading storage (tests). Omit to use getPreferredEmployeeAssignmentId(). */
  preferredAssignmentId?: string | null;
}): { effectiveId: string | null; needsPicker: boolean } {
  const { linkedSummaries, primaryAssignmentId, queryAssignmentId } = input;
  const unique = dedupeLinkedSummariesByAssignmentId(linkedSummaries);
  const linkedCount = unique.length;
  const allowed = new Set(
    unique.map((r) => r.assignment_id).filter((x): x is string => Boolean(x))
  );
  const primary = unique[0]?.assignment_id ?? primaryAssignmentId;

  if (queryAssignmentId && allowed.has(queryAssignmentId)) {
    return { effectiveId: queryAssignmentId, needsPicker: false };
  }

  const preferred =
    input.preferredAssignmentId !== undefined
      ? input.preferredAssignmentId
      : getPreferredEmployeeAssignmentId();
  const pref = (preferred || '').trim();
  if (pref && allowed.has(pref)) {
    return { effectiveId: pref, needsPicker: false };
  }

  if (linkedCount <= 1) {
    return { effectiveId: primary ?? null, needsPicker: false };
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
