import { test, expect } from '@playwright/test';
import { assertLogicalPage } from '../_helpers';

/**
 * Harness contract test for assertLogicalPage's B10 (permanent-spinner) check.
 * No network — uses page.setContent — so it's deterministic. Locks the cold-start
 * tolerance fix: a spinner that CLEARS within the window must NOT be flagged B10,
 * while one that NEVER clears MUST be. Guards against either regression (the old
 * single-5s recheck false-flagged slow cold-start loads; over-loosening would hide
 * a genuinely stuck page).
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

  test('a spinner that never clears IS flagged B10 (genuinely stuck)', async ({ page }, info) => {
    await page.setContent('<h1>Services</h1><div class="animate-spin" id="sp">Loading…</div>');
    const v = await assertLogicalPage(page, info, 'selftest-stuck');
    expect(v.signals, `signals: ${v.signals}`).toContain('permanent-spinner(B10)');
  });
});
