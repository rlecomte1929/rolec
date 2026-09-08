import { test, expect } from '@playwright/test';
import { assertLogicalPage } from '../_helpers';

/**
 * Harness contract test for assertLogicalPage's B10 (permanent-spinner) check.
 * No network — uses page.setContent + an injected `probeHealthy`/`spinnerClearMs` — so
 * it's deterministic. Locks two fixes: (a) the cold-start tolerance — a spinner that
 * CLEARS within the window must NOT be flagged B10, while one that NEVER clears MUST be;
 * and (b) the deploy-window tolerance (symmetric with B13) — a never-clearing spinner
 * while the backend is DOWN is environmental (not a bug), but the SAME spinner while the
 * backend is HEALTHY is still a genuine B10.
 */
test.describe('assertLogicalPage — B10 cold-start tolerance', () => {
  test('a spinner that clears within the window is NOT flagged B10 (slow ≠ stuck)', async ({ page }, info) => {
    await page.setContent('<h1>Services</h1><div class="animate-spin" id="sp">Loading…</div>');
    // simulate a slow-but-resolving load: the spinner disappears after ~2s.
    await page.evaluate(() => {
      setTimeout(() => document.getElementById('sp')?.remove(), 2000);
    });
    const v = await assertLogicalPage(page, info, 'selftest-clears');
    expect(v.signals, `signals: ${v.signals}`).not.toContain('permanent-spinner(B10)');
    expect(v.heading).toBe('Services');
  });

  test('a spinner that never clears + backend HEALTHY IS flagged B10 (genuinely stuck)', async ({ page }, info) => {
    await page.setContent('<h1>Services</h1><div class="animate-spin" id="sp">Loading…</div>');
    const v = await assertLogicalPage(page, info, 'selftest-stuck', {
      probeHealthy: async () => true,
      spinnerClearMs: 300,
    });
    expect(v.signals, `signals: ${v.signals}`).toContain('permanent-spinner(B10)');
    expect(v.signals, `signals: ${v.signals}`).not.toContain('backend-unavailable(env)');
    expect(info.annotations.some((a) => a.type === 'environmental')).toBe(false);
  });

  test('a spinner that never clears + backend DOWN → environmental, NOT B10 (deploy window)', async ({ page }, info) => {
    await page.setContent('<h1>Services</h1><div class="animate-spin" id="sp">Loading…</div>');
    const v = await assertLogicalPage(page, info, 'selftest-stuck-down', {
      probeHealthy: async () => false,
      spinnerClearMs: 300,
    });
    expect(v.signals, `signals: ${v.signals}`).toContain('backend-unavailable(env)');
    expect(v.signals, `signals: ${v.signals}`).not.toContain('permanent-spinner(B10)');
    // the environmental annotation must be recorded so the ingest can reclassify FAIL→ENV
    expect(info.annotations.some((a) => a.type === 'environmental')).toBe(true);
  });
});
