import { describe, it, expect, beforeEach } from 'vitest';
import { openCaseHref, setLastVisited } from '../employeeCaseProgress';

/**
 * AIQ-976: "Open case" on the employee dashboard must route to the
 * case-scoped wizard so multi-case employees open the row they clicked,
 * not the generic /employee/intake page (which renders the primary case
 * from EmployeeAssignmentContext regardless of the row).
 *
 * jsdom here runs with an opaque origin and does not expose
 * window.localStorage, so we install a minimal in-memory shim — the source
 * uses window.localStorage and swallows failures, so this also exercises
 * the real getLastVisited/setLastVisited round-trip.
 */
function installLocalStorage(): void {
  const store = new Map<string, string>();
  const mock = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  };
  Object.defineProperty(window, 'localStorage', { value: mock, configurable: true });
}

describe('openCaseHref', () => {
  beforeEach(() => {
    installLocalStorage();
  });

  it('routes pre-intake "assigned" cases to the case-scoped wizard', () => {
    expect(openCaseHref('case-abc', 'assigned')).toBe('/employee/case/case-abc/wizard');
  });

  it('routes pre-intake "awaiting_intake" cases to the case-scoped wizard', () => {
    expect(openCaseHref('case-xyz', 'awaiting_intake')).toBe('/employee/case/case-xyz/wizard');
  });

  it('uses the per-case id (two different rows resolve to different routes)', () => {
    expect(openCaseHref('case-1', 'assigned')).not.toBe(openCaseHref('case-2', 'assigned'));
  });

  it('falls back to the case summary for started cases with no last-visited route', () => {
    expect(openCaseHref('case-abc', 'active')).toBe('/employee/case/case-abc/summary');
  });

  it('honors the last-visited route for started cases', () => {
    setLastVisited('case-abc', '/employee/case/case-abc/plan');
    expect(openCaseHref('case-abc', 'active')).toBe('/employee/case/case-abc/plan');
  });
});
