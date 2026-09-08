import { test, expect } from '@playwright/test';
import { trackConsoleErrors } from './support/console';

/**
 * QG-5a · no-backend smoke. Runs against the built `vite preview` (:4173) with NO
 * live backend — these specs only exercise client-side behaviour (boot, routing,
 * route guards, and the login UI with a mocked /api/auth/login). Deterministic and
 * flake-free, so they gate PRs. The authed page-render flows live in
 * smoke.authed.spec.ts (QG-5b) behind mocked /api data.
 */

const pathname = (url: string) => new URL(url).pathname;

test.describe('QG-5a · no-backend smoke', () => {
  test('app boots on the landing page without console errors', async ({ page }) => {
    const errors = trackConsoleErrors(page);
    await page.goto('/');
    await expect(page).toHaveURL(/:4173\/$/);
    // White-screen guard: the React root must have rendered real content.
    await expect(page.locator('#root')).not.toBeEmpty();
    await expect(page.locator('#root *')).not.toHaveCount(0);
    errors.assertClean();
  });

  test('login form renders at /auth', async ({ page }) => {
    await page.goto('/auth');
    await expect(page.locator('#auth-login-identifier')).toBeVisible();
    await expect(page.locator('#auth-login-password')).toBeVisible();
    // Scope to the form — "Sign in" also matches the login/register mode tab.
    await expect(page.locator('form').getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  for (const guardedPath of ['/employee/dashboard', '/hr/dashboard', '/admin']) {
    test(`route guard redirects unauthenticated ${guardedPath} → /`, async ({ page }) => {
      await page.goto(guardedPath);
      // The guard redirects client-side after mount — wait for the URL to settle.
      await page.waitForURL((url) => pathname(url) === '/', { timeout: 10_000 });
      expect(pathname(page.url())).toBe('/');
    });
  }

  test('login UI works (mocked login API) → employee dashboard', async ({ page }) => {
    // Catch-all so no real /api call escapes the preview; the specific login route
    // (registered last → matched first) returns a successful auth payload.
    await page.route('**/api/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    );
    await page.route('**/api/auth/login', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          token: 'e2e-mock-token',
          user: {
            id: 'emp-e2e',
            role: 'EMPLOYEE',
            email: 'e2e@test.relopass',
            username: 'e2e',
            name: 'E2E Employee',
          },
        }),
      }),
    );

    await page.goto('/auth');
    await page.locator('#auth-login-identifier').fill('e2e@test.relopass');
    await page.locator('#auth-login-password').fill('whatever');
    // Submit via Enter (matches support/auth.ts) — the submit button starts disabled.
    await page.locator('#auth-login-password').press('Enter');

    // homeRouteKeyForRole(EMPLOYEE) → /employee/dashboard
    await page.waitForURL(/\/employee\/dashboard/, { timeout: 15_000 });
    const token = await page.evaluate(() => localStorage.getItem('relopass_token'));
    expect(token).toBe('e2e-mock-token');
  });
});
