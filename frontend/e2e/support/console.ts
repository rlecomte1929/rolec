import { Page, expect } from '@playwright/test';

/**
 * Console / page-error noise that is known-benign in the preview build and not an
 * app regression — see repo memory (GoTrue singleton + LockManager test artifact).
 */
const BENIGN = [
  /Multiple GoTrueClient instances/i,
  /Navigator LockManager|lock.*timed out/i,
  /\[PostHog/i,
  /favicon\.ico/i,
  /Failed to load resource.*(404|the server responded)/i, // unmocked optional assets in preview
];

/**
 * Attach a console/pageerror collector to a page. Call `assertClean()` after the
 * page has settled to fail the test on any UNEXPECTED console error or uncaught
 * exception — the cheapest white-screen / boot-regression detector there is.
 */
export function trackConsoleErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && !BENIGN.some((re) => re.test(msg.text()))) {
      errors.push(`console.error: ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => {
    if (!BENIGN.some((re) => re.test(err.message))) {
      errors.push(`pageerror: ${err.message}`);
    }
  });
  return {
    assertClean() {
      expect(errors, `unexpected console errors:\n${errors.join('\n')}`).toEqual([]);
    },
  };
}
