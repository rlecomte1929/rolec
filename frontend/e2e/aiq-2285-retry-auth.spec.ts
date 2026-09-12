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
    await page.getByRole('button', { name: /try again/i }).click();
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
});
