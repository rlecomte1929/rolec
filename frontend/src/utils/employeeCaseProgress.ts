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
 * actively works in (summary, wizard/N, plan). As of AIQ-1249 the services
 * flow is also case-id-native (/employee/case/<id>/services/...), so its
 * last-visited entries are stored in the same case-scoped form — still keyed
 * by assignmentId. The legacy /services/... URLs remain valid as redirecting
 * back-compat aliases.
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
