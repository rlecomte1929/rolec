import { test, expect } from '@playwright/test';
import { seedAuth } from './support/auth';
import { mockApi } from './support/mockApi';
/**
 * AIQ-2285 — Try again on the employee dashboard must not paint the admin
 * console on a /auth URL. 403 stays in place; a real 401 shows the login form.
 */
test.describe('AIQ-2285 retry / auth coherence', () => {
  test('403 overview retry stays on the employee dashboard', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {});
    await page.route('**/api/employee/assignments/overview', (route) =>
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Insufficient permissions' }),
      }),
    );

    await page.goto('/employee/dashboard');
    // Heading only — the body also contains "cannot open employee assignments",
    // so a combined getByText regex is a Playwright strict-mode violation.
    await expect(page.getByRole('heading', { name: /could not load assignments/i })).toBeVisible();
    await expect(page.getByText(/this account cannot open employee assignments/i)).toBeVisible();
    // 403 is not transient — retry would loop the same forbidden response.
    await expect(page.getByRole('button', { name: /try again/i })).toHaveCount(0);
    await expect(page).toHaveURL(/\/employee\/dashboard/);
    await expect(page.getByRole('heading', { name: /sign in/i })).toHaveCount(0);
    await expect(page.getByText(/content review pending/i)).toHaveCount(0);
  });

  test('401 overview shows the login form at /auth, not the admin console', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {});
    await page.route('**/api/employee/assignments/overview', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid token' }),
      }),
    );

    await page.goto('/employee/dashboard');
    await expect(page).toHaveURL(/\/auth\?mode=login&reason=session_expired/);
    await expect(page.getByRole('heading', { name: /sign in to relopass/i })).toBeVisible();
    await expect(page.getByText(/content review pending/i)).toHaveCount(0);
    await expect(page.getByText(/founder console/i)).toHaveCount(0);
  });

  // A failed overview reports linkedCount 0, and the dashboard derives
  // "you have no case" from that count. Without gating, the manual-claim
  // onboarding renders underneath the error alert and tells a relocating
  // employee their case does not exist.
  test('an errored overview never renders the "link your case" onboarding', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {});
    await page.route('**/api/employee/assignments/overview', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'boom' }) }),
    );

    await page.goto('/employee/dashboard');
    await expect(page.getByRole('heading', { name: /could not load assignments/i })).toBeVisible();
    await expect(page.locator('#employee-unlinked-empty-state')).toHaveCount(0);
    await expect(page.getByTestId('employee-case-link-instruction')).toHaveCount(0);
    await expect(page.getByText(/assignment status/i)).toHaveCount(0);
  });

  // The backend swallows a build failure into HTTP 200 + overview_degraded, so a
  // successful-looking response can carry zero rows it does not stand behind.
  test('a degraded 200 shows the degraded notice, not an empty-state claim', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {});
    await page.route('**/api/employee/assignments/overview', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ linked: [], pending: [], overview_degraded: true }),
      }),
    );

    await page.goto('/employee/dashboard');
    await expect(page.getByRole('heading', { name: /could not load assignments/i })).toBeVisible();
    await expect(page.getByText(/nothing has changed on your cases/i)).toBeVisible();
    await expect(page.locator('#employee-unlinked-empty-state')).toHaveCount(0);
    // Degraded is transient, so the retry affordance must stay.
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  // Guard against the fix over-reaching: a genuine empty overview must still
  // show the onboarding, or new employees lose their way to link a case.
  test('a resolved empty overview still shows the onboarding', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {});
    await page.route('**/api/employee/assignments/overview', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ linked: [], pending: [] }) }),
    );

    await page.goto('/employee/dashboard');
    await expect(page.getByRole('heading', { name: /could not load assignments/i })).toHaveCount(0);
    await expect(page.locator('#employee-unlinked-empty-state')).toBeVisible();
  });
});
