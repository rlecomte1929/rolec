import { describe, it, expect, vi } from 'vitest';

// Mock the heavy/side-effecting deps so this test doesn't pull in api/client (→ supabase
// import trap) or the perf module. errorTracking is left REAL to verify PII scrubbing.
vi.mock('../../api/requestLog', () => ({
  getRecentFailedRequests: () => [
    {
      method: 'POST',
      path: '/api/users/11111111-1111-1111-1111-111111111111',
      status: 500,
      requestId: 'req-1',
      ts: 't',
    },
  ],
}));
vi.mock('../../perf/perf', () => ({ getCurrentInteractionId: () => 'int-1' }));

import { collectDiagnostics } from '../diagnostics';
import { reportError, getRecentErrors } from '../errorTracking';

describe('collectDiagnostics', () => {
  it('returns a snapshot with correlation id + failed requests, PII-scrubbed', () => {
    const ctx = collectDiagnostics();
    expect(typeof ctx.appVersion).toBe('string');
    expect(ctx.interactionId).toBe('int-1');
    expect(ctx.recentFailedRequests).toHaveLength(1);
    expect(ctx.recentFailedRequests[0]!.status).toBe(500);
    // the UUID in the failed-request path is scrubbed before it leaves the browser
    expect(ctx.recentFailedRequests[0]!.path).toBe('/api/users/[id]');
    expect(typeof ctx.route).toBe('string');
    expect(Array.isArray(ctx.breadcrumbs)).toBe(true);
    expect(Array.isArray(ctx.recentErrors)).toBe(true);
  });
});

describe('errorTracking recent-errors buffer', () => {
  it('captures the failing function (first user-code stack frame)', async () => {
    await reportError({
      message: 'boom',
      stack: 'Error: boom\n    at doThing (SomeWidget.tsx:12:5)\n    at n (vendor.js:1:1)',
    });
    const errs = getRecentErrors();
    expect(errs.length).toBeGreaterThan(0);
    expect(errs[errs.length - 1]!.failingFrame).toContain('SomeWidget.tsx');
  });
});
