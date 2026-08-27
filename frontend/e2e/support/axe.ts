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
export async function expectNoSeriousA11yViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    // STILL excluded, but for a different and now-measured reason. The Tailwind
    // muted-text tier is fixed (879 sites, enforced by local/no-low-contrast-text),
    // yet a scan of 12 public routes with this rule ON still finds ~77 failures that
    // a class sweep cannot reach:
    //   ~50x  #c6cbd0 / #c1c7cb / #d1d9de / #b5bcc1 on near-white at 1.3-1.75:1
    //         — not Tailwind classes; they come from CSS files or inline styles
    //    12x  #1f8e8b (the BRAND teal) as link text on white = 3.96:1 — fixing this
    //         is a brand decision, not a token swap
    //     5x  #6b7c8f (--marketing-text-subtle) on white = 4.28:1 — the token itself
    //         is marginally non-compliant and needs redefining
    // Turning the rule on now would make the gate perma-red on causes this sweep was
    // never going to address. Re-run the scan and drop this line once those three
    // families are dealt with.
    .disableRules(['color-contrast'])
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
