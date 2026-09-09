import { expect, type Page } from '@playwright/test';
import { trackConsoleErrors } from './console';

/**
 * Robust authenticated-portal smoke, shared by the three `*.portal.spec.ts` files.
 *
 * The page arrives already authenticated via the project's `storageState` (written
 * once by `portals/auth.setup.ts`), so this asserts the things that actually break
 * an authed portal in prod — WITHOUT brittle per-portal selectors:
 *   1. the session held: the route guard did NOT bounce us to the sign-in screen;
 *   2. we are inside the requested portal;
 *   3. the login form is absent (belt-and-braces auth signal);
 *   4. the shell painted something (not a white screen / 500);
 *   5. the console is clean (cheapest boot-regression detector — see console.ts).
 *
 * Deeper per-role journeys (HR opens a case, Employee views the roadmap, Admin opens
 * the Countries CMS) are a deliberate follow-up — see docs/e2e-live-portals.md.
 */
export async function assertPortalReachable(
  page: Page,
  opts: { path: string; inPortal: RegExp },
): Promise<void> {
  const console_ = trackConsoleErrors(page);
  await page.goto(opts.path);
  await page.waitForLoadState('networkidle');

  await expect(page, 'auth session should hold — not redirected to sign-in').not.toHaveURL(
    /\/(login|sign-?in)(\/|\?|$)/,
  );
  await expect(page, `should be inside the ${opts.path} portal`).toHaveURL(opts.inPortal);
  await expect(
    page.locator('#auth-login-password'),
    'the login form should not be shown to an authenticated user',
  ).toHaveCount(0);
  await expect(page.locator('body'), 'the app shell should render, not a blank page').not.toBeEmpty();

  console_.assertClean();
}
