/**
 * Employee case progress: remember where the employee was last in the
 * relocation flow so "Open case" routes them back, not to step 1.
 *
 * Storage: localStorage, per (assignmentId). Picked over a server-side
 * column for v1 because:
 *   - It works immediately with no backend change.
 *   - It's user-scoped naturally (browser session).
 *   - It's cheap to read on every dashboard render.
 *
 * Tradeoffs accepted: no cross-device resume, no cross-browser resume,
 * lost on browser data clear. Acceptable for first pilot. If we need
 * cross-device persistence later, swap to a `case_assignments.last_visited_route`
 * column with the same public API.
 *
 * Routes we track: any /employee/case/<id>/<segment> URL the user
 * actively works in (summary, wizard/N, plan). Services routes are
 * separately tracked because they live under /services/ not /employee/.
 */

const STORAGE_PREFIX = 'relopass_last_visited_';

/** Earliest version we'd want to invalidate stale entries from. */
const SCHEMA_VERSION = 1;

type StoredEntry = {
  v: number;
  route: string;
  // ISO timestamp; lets us evict entries older than e.g. 30 days if we
  // ever want to. Not enforced today; useful for diagnostics.
  ts: string;
};

function _key(assignmentId: string): string {
  return `${STORAGE_PREFIX}${assignmentId}`;
}

/**
 * Save the route the employee just landed on. Idempotent: writing the
 * same route is a no-op storage write but cheap. Throws nothing — local
 * storage failures (private mode, quota) are swallowed because the
 * fallback (always landing on step 1) is acceptable.
 */
export function setLastVisited(assignmentId: string, route: string): void {
  if (!assignmentId || !route) return;
  try {
    const entry: StoredEntry = {
      v: SCHEMA_VERSION,
      route,
      ts: new Date().toISOString(),
    };
    window.localStorage.setItem(_key(assignmentId), JSON.stringify(entry));
  } catch {
    // ignore — see module doc
  }
}

/**
 * Read the last route stored for this assignment, or null if none / invalid.
 * Caller is responsible for falling back to a sensible default route.
 */
export function getLastVisited(assignmentId: string): string | null {
  if (!assignmentId) return null;
  try {
    const raw = window.localStorage.getItem(_key(assignmentId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredEntry>;
    if (parsed.v !== SCHEMA_VERSION) return null;
    if (typeof parsed.route !== 'string' || !parsed.route) return null;
    return parsed.route;
  } catch {
    return null;
  }
}

/** Clear when the user explicitly resets, or when the assignment closes. */
export function clearLastVisited(assignmentId: string): void {
  if (!assignmentId) return;
  try {
    window.localStorage.removeItem(_key(assignmentId));
  } catch {
    // ignore
  }
}

/**
 * Resolve where to send the user when they click "Open case" (or the
 * Continue / Start links) on the dashboard. Honor the last route they
 * visited inside this assignment so re-entering doesn't force them through
 * the wizard again; fall back to the case summary page otherwise.
 *
 * Both `assigned` (fresh assignment from HR, intake not started) and
 * `awaiting_intake` (intake started but not submitted) are pre-intake
 * states whose entry point is the wizard — send both to step 1 rather than
 * the (empty) summary or a stale last-visited URL.
 *
 * AIQ-976: the pre-intake target must be the case-scoped wizard, not the
 * generic `/employee/intake` route — that page reads the *primary* case
 * from EmployeeAssignmentContext, so for a multi-case employee every row
 * opened the same (first) case. Routing to `/employee/case/{id}/wizard`
 * opens the row that was actually clicked.
 */
export function openCaseHref(assignmentId: string, status?: string | null): string {
  if (status === 'awaiting_intake' || status === 'assigned') {
    return `/employee/case/${assignmentId}/wizard`;
  }
  return getLastVisited(assignmentId) || `/employee/case/${assignmentId}/summary`;
}
