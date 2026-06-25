import { Page } from '@playwright/test';

/**
 * Log in through the real ReloPass login form so every auth artefact the app
 * relies on (the `relopass_token` session token, role, Supabase mirror) is set
 * exactly as in production — more robust than injecting localStorage by hand.
 *
 * Creds default to the demo employee and can be overridden via env.
 */
export const EMPLOYEE_EMAIL = process.env.E2E_EMPLOYEE_EMAIL || 'employee@testingapril.com';
const EMPLOYEE_PASSWORD = process.env.E2E_EMPLOYEE_PASSWORD || 'EmpPass!1';

export async function loginAsEmployee(page: Page): Promise<void> {
  await page.goto('/login');
  await page.locator('#auth-login-identifier').fill(EMPLOYEE_EMAIL);
  await page.locator('#auth-login-password').fill(EMPLOYEE_PASSWORD);
  await page.locator('#auth-login-password').press('Enter');
  // The login round-trip persists the ReloPass session token; gate on it before
  // navigating so we never race the auth context.
  await page.waitForFunction(() => !!localStorage.getItem('relopass_token'), undefined, {
    timeout: 20_000,
  });
}
