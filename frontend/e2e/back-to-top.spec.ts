import { test, expect, type Page } from '@playwright/test';

/**
 * Regression cover for the floating "Back to top" control
 * (`src/components/public/BackToTop.tsx`, mounted for every public route via
 * `PublicLayout`).
 *
 * WHY THIS EXISTS
 * ---------------
 * PR #2071 fixed a real defect: at narrow widths the ~110px control sits over the centred
 * `max-w-2xl` marketing forms and swallows taps meant for their inputs — reported against
 * `#inline-demo-company` on /access. The fix was one Tailwind token, `hidden sm:flex`, and
 * nothing pinned it.
 *
 * It was then re-reported (AIQ-2163) with a fabricated mechanism: that the control is stuck at
 * `opacity: 0` because its `animate-fade-in` keyframe "never starts", while remaining
 * `pointer-events: auto` and hit-testable. That is not how this component works — visibility is
 * `useState` + `if (!visible) return null`, so when hidden there is no DOM node at all, and the
 * animation only ever runs on an element that is already committed. Acting on that brief would
 * have meant keeping the button mounted in an opacity-0 state, which is exactly the
 * always-mounted overlay #2071 removed.
 *
 * So these three assertions pin the properties that make both the original bug and the
 * fabricated one impossible. Cases 1 and 2 are the same control at two viewports with opposite
 * expected outcomes, which is what stops either from being vacuous.
 */

// `animate-fade-in` is a real 0.2s animation. Asserting opacity mid-fade is the flake that cost
// two rounds on the axe gate earlier; reduced motion is also a genuine user setting.
test.use({ reducedMotion: 'reduce' });

const MOBILE = { width: 375, height: 720 };
const DESKTOP = { width: 1280, height: 720 };

/** Scroll past the component's 30%-of-viewport-height threshold and let its listener settle. */
async function scrollPastThreshold(page: Page): Promise<void> {
  await page.evaluate(() => window.scrollTo(0, Math.ceil(window.innerHeight * 0.9)));
  await page.waitForFunction(() => window.scrollY > window.innerHeight * 0.3);
}

test.describe('QG-14 · floating "Back to top" control', () => {
  // TWO locators on purpose, and the distinction is load-bearing.
  // getByRole matches the ACCESSIBILITY TREE, which excludes display:none nodes — so at mobile
  // width (`hidden sm:flex`) a role locator reports the control as absent, and any
  // "is it hidden / is it in the DOM" assertion written with it would pass vacuously, for the
  // wrong reason. DOM-presence questions therefore use the attribute selector; the desktop
  // visibility assertion keeps the role locator, where being in the a11y tree is the point.
  const inDom = (page: Page) => page.locator('[aria-label="Back to top"]');
  const byRole = (page: Page) => page.getByRole('button', { name: 'Back to top' });

  test('is absent from the DOM before the scroll threshold', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto('/privacy');
    await expect(page.locator('#root *')).not.toHaveCount(0);
    // Not merely hidden — `if (!visible) return null`. This is the property that makes the
    // "invisible but still hit-testable" report impossible, so it must be asserted against the
    // DOM, not the a11y tree.
    await expect(inDom(page)).toHaveCount(0);
  });

  test('becomes visible past the threshold on desktop', async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto('/privacy');
    await expect(page.locator('#root *')).not.toHaveCount(0);
    await scrollPastThreshold(page);

    await expect(byRole(page)).toBeVisible();
    await expect(byRole(page)).toHaveCSS('opacity', '1');
  });

  // The defect PR #2071 actually fixed.
  test('never covers the demo form input at mobile width', async ({ page }) => {
    await page.setViewportSize(MOBILE);
    await page.goto('/access');
    const companyInput = page.locator('#inline-demo-company');
    await expect(companyInput).toBeVisible();

    // Scroll the form into view rather than an arbitrary offset. That is what a user does, and
    // it clears the 30% threshold on the way (the field sits ~1400px down a 720px viewport), so
    // the control is mounted at the moment we assert it cannot be seen or touched.
    await companyInput.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => window.scrollY > window.innerHeight * 0.3);
    // toBeAttached, not a synchronous query: waitForFunction resolves the moment scrollY
    // crosses the threshold, which is before React has committed the re-render.
    await expect(inDom(page)).toBeAttached();

    // Past the threshold the element mounts, but `hidden sm:flex` keeps it display:none here.
    await expect(inDom(page)).toBeHidden();

    // display:none yields a zero rect, so it cannot intercept anything. Assert the geometry
    // rather than trusting the class: a later refactor could keep the class and still paint a
    // box. Measured in-page — locator.boundingBox() *waits* for visibility and would just time
    // out here rather than reporting the absence we are asserting.
    const rect = await page.evaluate(() => {
      const el = document.querySelector('[aria-label="Back to top"]');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { w: r.width, h: r.height };
    });
    expect(rect === null || (rect.w === 0 && rect.h === 0)).toBe(true);

    // And the input is genuinely reachable at its own centre.
    const box = await companyInput.boundingBox();
    expect(box).not.toBeNull();
    const hit = await page.evaluate(
      ([x, y]) => (document.elementFromPoint(x, y) as HTMLElement | null)?.id ?? '',
      [box!.x + box!.width / 2, box!.y + box!.height / 2] as const,
    );
    expect(hit).toBe('inline-demo-company');
  });
});
