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

/**
 * Map a resolved assignment id back to its canonical case_id for **case-scoped**
 * endpoints — e.g. `GET/PUT /api/cases/{caseId}/services-state`. The services
 * pages resolve an `assignment_id` (via resolveScopedAssignmentId) but the
 * services-state route is keyed by case_id; passing the assignment_id 404s
 * ("Case not found"). Resolve via linkedSummaries.
 *
 * AIQ-1704: returns `null` on a miss (was: the raw id). The raw-id fallback was
 * the documented "fallback hole" — on a miss the id is often the *assignment* id,
 * which a case-keyed endpoint reads as the wrong case. Callers that still want the
 * raw id as a last resort do so explicitly (`?? pathCaseId`, `?? id`); a bare miss
 * now fails closed instead of silently returning an assignment id. (AIQ-1320)
 */
export function caseIdForAssignment(
  linkedSummaries: EmployeeLinkedOverviewRow[],
  id: string | null,
): string | null {
  if (!id) return null;
  const row = linkedSummaries.find((r) => r.assignment_id === id || r.case_id === id);
  return row?.case_id ?? null;
}

/**
 * First case_id the employee actually owns among `candidates` (URL, last-selected,
 * primary). Never returns a stale localStorage / HR-viewed UUID when this account
 * has no linked assignment (AIQ-2358 / AIQ-2359).
 */
export function ownedEmployeeCaseId(
  linkedSummaries: EmployeeLinkedOverviewRow[],
  candidates: Array<string | null | undefined>,
): string | null {
  for (const candidate of candidates) {
    const id = caseIdForAssignment(linkedSummaries, candidate ?? null);
    if (id) return id;
  }
  return linkedSummaries[0]?.case_id ?? null;
}

/**
 * The case_id to PERSIST case-scoped state against (services-state), or `null`
 * when it cannot be safely resolved yet.
 *
 * AIQ-1691: `caseIdForAssignment` falls back to the raw `id` on a miss. While the
 * linked summaries are still loading, that raw id is the **assignment_id** — and
 * `POST /api/cases/{assignmentId}/services-state` 404s ("Case not found"), so
 * debounced saves that fire in the load window are silently dropped and the
 * shortlist persists incomplete (only the writes AFTER the summaries load land).
 * This gate returns `null` until the summaries have loaded, so the caller skips
 * the save (localStorage still holds the state) and persists once — with the real
 * case_id — after resolution. Once loaded, a genuine legacy no-match still falls
 * back to the id, which for a case_id URL is correct.
 *
 * AIQ-1704: `caseIdForAssignment` now returns `null` on a miss (fail closed), so
 * this gate re-adds the post-load raw-id fallback explicitly to preserve the
 * documented legacy-case_id-URL behaviour above — the mid-load guard (the actual
 * AIQ-1691 fix) is unchanged.
 */
export function persistableCaseId(
  linkedSummaries: EmployeeLinkedOverviewRow[],
  id: string | null,
  summariesLoaded: boolean,
): string | null {
  if (!id) return null;
  if (!summariesLoaded) return null; // don't guess mid-load — a wrong (assignment) id 404s
  return caseIdForAssignment(linkedSummaries, id) ?? id;
}

/**
 * Inverse of {@link caseIdForAssignment}: map a scope id — which may be a
 * **case_id** (the canonical employee URL id, AIQ-1334) or an assignment_id — to
 * its assignment_id. Lets the services pages accept a case_id in the URL while
 * still resolving the assignment_id their APIs key on.
 *
 * AIQ-1704: returns `null` on a miss (was: the raw id) — fail closed. The sole
 * consumer, resolveScopedAssignmentId, guards its result with `allowed.has(...)`,
 * which already excludes any un-matched id, so this is behaviour-preserving there.
 */
export function assignmentIdForScopeId(
  linkedSummaries: EmployeeLinkedOverviewRow[],
  id: string | null,
): string | null {
  if (!id) return null;
  const row = linkedSummaries.find((r) => r.assignment_id === id || r.case_id === id);
  return row?.assignment_id ?? null;
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
  const { linkedSummaries, primaryAssignmentId } = input;
  const unique = dedupeLinkedSummariesByAssignmentId(linkedSummaries);
  const linkedCount = unique.length;
  const allowed = new Set(
    unique.map((r) => r.assignment_id).filter((x): x is string => Boolean(x))
  );
  const primary = unique[0]?.assignment_id ?? primaryAssignmentId;

  // AIQ-1334: the path id may be a case_id (the canonical employee URL id) or an
  // assignment_id — normalize to the assignment_id so either resolves.
  const queryAssignmentId = assignmentIdForScopeId(linkedSummaries, input.queryAssignmentId);

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
