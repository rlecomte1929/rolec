import { test, expect, Page } from '@playwright/test';
import { mockApi } from './support/mockApi';

/**
 * AIQ-1711 · the welcome dismissal survives a new device.
 *
 * AIQ-1701 made the first-login welcome durable per USER: the login response carries
 * `welcome_seen` (from `profiles.welcome_seen_at`) and `useAuth.setSession` mirrors it
 * into localStorage via `seedWelcomeSeenFromLogin`, which is what the SYNCHRONOUS
 * `useWelcomeRedirect` check reads on the role home. Its headline promise — a returning
 * user on a NEW browser is not re-onboarded — was only ever confirmed by a manual
 * incognito login. This codifies it.
 *
 * Every context Playwright creates is a fresh profile with empty localStorage, so
 * "a new device" is the default state here — exactly the case that used to re-onboard.
 *
 * Why this drives the REAL login form instead of `seedAuth()`: the seed runs on the
 * LOGIN path only. `seedAuth()` writes the auth keys directly and never calls
 * `setSession`, so it would sail past the very code under test — it would model the
 * pre-AIQ-1701 bug rather than catch it.
 *
 * Hermetic: `**\/api/auth/login` is mocked, so there is no backend and no real password.
 * The identifier is deliberately NOT an email and the mocked user carries no `email`,
 * which makes `useAuth`'s `if (email && payload.password)` Supabase branch fall through
 * — no network call to the placeholder Supabase host.
 */

type Role = 'HR' | 'EMPLOYEE';

const ROLE_HOME: Record<Role, RegExp> = {
  HR: /\/hr\/dashboard/,
  EMPLOYEE: /\/employee\/dashboard/,
};
const WELCOME_PATH: Record<Role, RegExp> = {
  HR: /\/hr\/welcome/,
  EMPLOYEE: /\/employee\/welcome/,
};
/** Any welcome route — used for the negative assertions, so a wrong-role redirect also fails. */
const ANY_WELCOME = /\/(hr|employee)\/welcome/;

/** Record every URL the page navigates to, so we can prove a route was NEVER visited. */
function trackNavigations(page: Page): { urls: string[] } {
  const urls: string[] = [];
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) urls.push(frame.url());
  });
  return { urls };
}

/**
 * Log in through the real form with a mocked backend.
 *
 * `welcomeSeen` is what the server would report from `profiles.welcome_seen_at`.
 * Everything else is the minimum `LoginResponse` shape (backend/schemas.py).
 */
async function loginWithMockedResponse(
  page: Page,
  role: Role,
  welcomeSeen: boolean,
): Promise<void> {
  await mockApi(page, {
    '**/api/auth/login': {
      token: 'e2e session token',
      user: {
        id: 'e2e-user',
        username: 'e2e',
        role,
        roles: [role],
        primary_role: role,
        name: 'E2E User',
        welcome_seen: welcomeSeen,
        // NOTE: no `email` — keeps useAuth's Supabase sign-in branch unreachable.
      },
    },
  });

  await page.goto('/login');
  // Not an email address, on purpose — see the module docblock.
  await page.locator('#auth-login-identifier').fill(`e2e-${role.toLowerCase()}`);
  await page.locator('#auth-login-password').fill('e2e placeholder');
  await page.locator('#auth-login-password').press('Enter');

  // Gate on the session token so we never race the post-login redirect.
  await page.waitForFunction(() => !!localStorage.getItem('relopass_token'), undefined, {
    timeout: 20_000,
  });
}

test.describe('AIQ-1711 · welcome dismissal survives a new device', () => {
  for (const role of ['HR', 'EMPLOYEE'] as Role[]) {
    test(`${role}: welcome_seen=true → a fresh context is NOT re-onboarded`, async ({ page }) => {
      const nav = trackNavigations(page);
      await loginWithMockedResponse(page, role, true);

      // Lands on the role home…
      await expect(page).toHaveURL(ROLE_HOME[role]);
      // …and stays there. useWelcomeRedirect runs in a mount effect, so settle before
      // asserting the negative — otherwise we would pass simply by looking too early.
      await page.waitForTimeout(1_000);
      await expect(page).not.toHaveURL(ANY_WELCOME);

      // Case C — no redirect-then-bounce: the welcome route was never even transiently
      // visited. A URL-at-the-end check alone would miss a flash that corrected itself.
      const flashes = nav.urls.filter((u) => ANY_WELCOME.test(u));
      expect(
        flashes,
        `the welcome page flashed before bouncing back — the redirect check is no longer ` +
          `synchronous. Navigations seen:\n${nav.urls.join('\n')}`,
      ).toEqual([]);
    });

    test(`${role}: welcome_seen=false → the welcome page IS shown once`, async ({ page }) => {
      const nav = trackNavigations(page);
      await loginWithMockedResponse(page, role, false);

      // The counter-case. Without it, a test that simply never redirects would pass
      // criterion 2 while the feature was entirely broken.
      await expect(page).toHaveURL(WELCOME_PATH[role]);

      const welcomeVisits = nav.urls.filter((u) => WELCOME_PATH[role].test(u));
      expect(welcomeVisits.length, `expected exactly one welcome navigation, saw ${welcomeVisits.length}`)
        .toBe(1);
    });
  }
});
