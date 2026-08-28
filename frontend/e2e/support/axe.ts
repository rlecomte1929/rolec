import AxeBuilder from '@axe-core/playwright';
import { Page, expect } from '@playwright/test';

/**
 * QG-9 · runtime accessibility gate. Runs axe-core (via @axe-core/playwright)
 * against the current page and fails the test on SERIOUS or CRITICAL violations
 * only — the initial low-noise threshold (per AIQ-1182 / AP-03). Moderate/minor
 * findings are surfaced by the jsx-a11y lint epic (AIQ-1234), not this gate.
 *
 * Reused by a11y.axe.spec.ts; pairs with the QG-5 preview+Playwright harness
 * (seedAuth + mockApi) so each page is checked in its real rendered state.
 */

// axe impact levels we block on. axe's impact is 'minor'|'moderate'|'serious'|'critical'.
const BLOCKING_IMPACTS = new Set(['serious', 'critical']);

/**
 * Analyze the current page with axe (WCAG 2.0/2.1/2.2 A + AA rules) and assert
 * there are no serious/critical violations. On failure the assertion message
 * lists each blocking violation compactly (impact, rule id, help text, node
 * count, help URL) so the CI log points straight at the fix.
 *
 * Call AFTER the page has settled (e.g. an `await expect(locator).toBeVisible()`)
 * so axe scans the fully-rendered DOM.
 */
/**
 * Wait for CSS transitions/animations to finish before scanning.
 *
 * Without this, axe samples elements mid-animation. The marketing pages wrap almost
 * everything in `FadeIn` (a staggered opacity transition), and a scan taken during the
 * ramp reports every faded element as a contrast failure — ~50 phantom violations in one
 * 12-route sweep. Chromium's getAnimations() includes CSS transitions, which is what
 * FadeIn uses.
 *
 * Bounded by a timeout: an intentionally infinite animation (a spinner, a pulse) would
 * otherwise hang the gate forever.
 */
async function settleAnimations(page: Page, timeoutMs = 2000): Promise<void> {
  await page.evaluate(async (ms) => {
    const finished = document.getAnimations().map((a) => a.finished.catch(() => undefined));
    await Promise.race([
      Promise.all(finished),
      new Promise((resolve) => setTimeout(resolve, ms)),
    ]);
  }, timeoutMs);
}

export async function expectNoSeriousA11yViolations(page: Page): Promise<void> {
  await settleAnimations(page);
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();

  const blocking = results.violations.filter((v) => BLOCKING_IMPACTS.has(v.impact ?? ''));

  const summary = blocking
    .map(
      (v) =>
        `  [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node(s))\n    ${v.helpUrl}`,
    )
    .join('\n');

  // Assert on the rule-id list (small, readable diff); full detail rides in the
  // message so the failing CI log is self-explanatory.
  expect(
    blocking.map((v) => v.id),
    `serious/critical a11y violations on ${page.url()}:\n${summary}`,
  ).toEqual([]);
}
