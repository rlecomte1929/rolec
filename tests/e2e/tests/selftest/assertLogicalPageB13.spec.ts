import { test, expect } from '@playwright/test';
import { assertLogicalPage } from '../_helpers';

/**
 * Harness contract test for assertLogicalPage's B13 deploy-tolerance (Signal A).
 * No network — uses page.setContent + an injected `probeHealthy` stub — so it's
 * deterministic. Locks the fix: an error page shown WHILE the backend is down (a
 * Render rolling-restart window) must be classified environmental (not a bug), while
 * the SAME error page shown while the backend is healthy must still be a real
 * raw-error-no-retry(B13). Guards against either regression (the old no-tolerance B13
 * false-flagged every deploy window; over-loosening would hide a genuine broken page).
 */
const ERROR_DOM = '<h1>Dashboard</h1><div>Something went wrong. Unexpected error (500).</div>';

test.describe('assertLogicalPage — B13 deploy-window tolerance (Signal A)', () => {
  test('error page + backend DOWN → environmental, NOT B13', async ({ page }, info) => {
    await page.setContent(ERROR_DOM);
    const v = await assertLogicalPage(page, info, 'selftest-b13-down', {
      probeHealthy: async () => false,
    });
    expect(v.signals, `signals: ${v.signals}`).toContain('backend-unavailable(env)');
    expect(v.signals, `signals: ${v.signals}`).not.toContain('raw-error-no-retry(B13)');
    // the environmental annotation must be recorded so the ingest can reclassify to ENV
    expect(info.annotations.some((a) => a.type === 'environmental')).toBe(true);
  });

  test('error page + backend HEALTHY → real B13 (not masked)', async ({ page }, info) => {
    await page.setContent(ERROR_DOM);
    const v = await assertLogicalPage(page, info, 'selftest-b13-up', {
      probeHealthy: async () => true,
    });
    expect(v.signals, `signals: ${v.signals}`).toContain('raw-error-no-retry(B13)');
    expect(v.signals, `signals: ${v.signals}`).not.toContain('backend-unavailable(env)');
    expect(info.annotations.some((a) => a.type === 'environmental')).toBe(false);
  });

  test('healthy content page → neither signal (regression guard)', async ({ page }, info) => {
    await page.setContent('<h1>Dashboard</h1><p>You have 3 active cases.</p>');
    // probe should not even be consulted; pass one that would throw if called.
    const v = await assertLogicalPage(page, info, 'selftest-b13-ok', {
      probeHealthy: async () => {
        throw new Error('probeHealthy must not be called when there is no error state');
      },
    });
    expect(v.signals, `signals: ${v.signals}`).not.toContain('raw-error-no-retry(B13)');
    expect(v.signals, `signals: ${v.signals}`).not.toContain('backend-unavailable(env)');
    expect(v.heading).toBe('Dashboard');
  });
});
