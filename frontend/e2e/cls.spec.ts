/**
 * QG-11 · Cumulative Layout Shift gate.
 *
 * The qa.replay.io sweep filed five "content jumps when the API responds" bugs. There was
 * no way to prove any of them, and no way to stop them recurring: jsdom has no layout
 * engine, so a component test can assert a class is present but never that two states
 * actually occupy the same height. Only a real browser can measure this.
 *
 * Method: PerformanceObserver on 'layout-shift', summing entries that are NOT
 * hadRecentInput (user-initiated shifts are expected and excluded, per the Core Web
 * Vitals definition). Threshold 0.1 is the CWV "good" boundary.
 *
 * Routes are public-only on purpose — they need no auth or backend, so this gate stays
 * fast and cannot flake on fixture drift. The authenticated shifts (sidebar branding,
 * vendor filter bar) are covered by their own component-level reservations instead.
 */
import { test, expect, type Page } from '@playwright/test';

const THRESHOLD = 0.1;

const ROUTES = ['/', '/platform', '/why', '/how-it-works', '/access', '/privacy', '/security'];

async function measureCls(page: Page, path: string): Promise<number> {
  // Start observing BEFORE navigation so shifts during hydration are counted.
  await page.addInitScript(() => {
    (window as unknown as { __cls: number }).__cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const e = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (!e.hadRecentInput) {
          (window as unknown as { __cls: number }).__cls += e.value;
        }
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });

  await page.goto(path);
  await page.locator('#root *').first().waitFor({ timeout: 10_000 }).catch(() => {});
  // Let images decode, fonts swap and fade-ins finish — all of which shift layout.
  await page.evaluate(async () => {
    const anims = document.getAnimations().map((a) => a.finished.catch(() => undefined));
    await Promise.race([Promise.all(anims), new Promise((r) => setTimeout(r, 2000))]);
  });
  await page.waitForTimeout(500);

  return page.evaluate(() => (window as unknown as { __cls: number }).__cls);
}

test.describe('QG-11 · layout stability', () => {
  /**
   * The one reported shift that reproduces. Measured on main: the password field drops
   * 34px when the login error appears, because the panel is `flex flex-col justify-center`
   * — inserting the Alert re-centres the whole column, so the heading rises AND the form
   * falls. The user's cursor moves out from under them mid-typing.
   *
   * Note this shift is post-interaction, so it carries hadRecentInput and is excluded from
   * the CLS metric by definition. It is a usability bug, not a Core Web Vitals one, which
   * is exactly why the route-level budget below cannot catch it and this test is explicit.
   */
  test('/auth does not move the form when a login error appears', async ({ page }) => {
    await page.route('**/api/auth/login', (r) =>
      r.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid credentials' }),
      }));
    await page.goto('/auth');
    const password = page.locator('#auth-login-password');
    await password.waitFor();
    const before = await password.boundingBox();

    await page.locator('#auth-login-identifier').fill('a@b.com');
    await password.fill('wrong');
    // NOT getByRole('button', {name:/sign in/i}) — the mode toggle above the form is also
    // a button reading "Sign in", and .first() silently matches THAT, so the form never
    // submits and the test passes while proving nothing.
    await page.locator('form button[type="submit"]').click();

    await expect(page.getByText(/invalid credentials/i)).toBeVisible();
    const after = await password.boundingBox();
    expect(Math.abs(after!.y - before!.y), 'password field must not move').toBeLessThanOrEqual(1);
  });

  for (const route of ROUTES) {
    test(`${route} stays under the CLS budget`, async ({ page }) => {
      const cls = await measureCls(page, route);
      expect(cls, `${route} CLS=${cls.toFixed(4)} (budget ${THRESHOLD})`).toBeLessThan(THRESHOLD);
    });
  }
});
