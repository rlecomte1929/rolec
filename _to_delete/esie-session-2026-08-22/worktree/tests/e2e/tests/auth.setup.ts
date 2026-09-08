import { test as setup, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { PERSONAS } from '../personas';

/**
 * THE ONLY CREDENTIAL-TOUCHING FILE. For each persona it logs in once and saves
 * the authenticated session to playwright/.auth/<key>.json. Passwords come ONLY
 * from the env vars named in personas.ts (PW_TESTCO / PW_DEMO) — nothing is
 * hardcoded. A persona whose env var is unset is skipped (so you can run a
 * subset). Login form grounded in the live code: /auth, #auth-login-identifier,
 * #auth-login-password, "Sign in", success = localStorage.relopass_token set.
 */
const AUTH_DIR = path.join(__dirname, '..', 'playwright', '.auth');
fs.mkdirSync(AUTH_DIR, { recursive: true });

for (const p of PERSONAS) {
  setup(`auth: ${p.key} (${p.identifier})`, async ({ page }) => {
    const password = process.env[p.pwEnv];
    setup.skip(!password, `env var ${p.pwEnv} not set — skipping ${p.key}`);

    // Reuse an already-saved session: re-running `npm run auth` then only fills the
    // gaps (the flaky few), and `npm test` stops re-authing once all 9 exist.
    // Delete playwright/.auth/<key>.json to force a fresh login.
    const sessionPath = path.join(AUTH_DIR, `${p.key}.json`);
    setup.skip(fs.existsSync(sessionPath), `session already saved for ${p.key} — reusing`);

    // Gentle pacing: consecutive production logins can hit rate-limiting (B7).
    await page.waitForTimeout(1500);

    await page.goto('/auth');
    // /auth may alias to /login; ensure the form is present
    const id = page.locator('#auth-login-identifier');
    if (!(await id.isVisible().catch(() => false))) {
      await page.goto('/login');
    }
    await page.fill('#auth-login-identifier', p.identifier);
    await page.fill('#auth-login-password', password!);
    // The page has two "Sign in" buttons (a tab toggle + the form submit) — scope to
    // the form so we hit the submit button (Playwright's own disambiguation).
    await page.locator('form').getByRole('button', { name: /sign in/i }).click();

    // success signal: token in localStorage (route guards key off it). 60s for slow prod logins.
    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('relopass_token')), { timeout: 60_000, intervals: [500, 1000, 2000] })
      .toBeTruthy();

    // sanity: role matches expectation
    const role = await page.evaluate(() => localStorage.getItem('relopass_role'));
    expect(role, `role for ${p.key}`).toBe(p.role);

    await page.context().storageState({ path: sessionPath });
    console.log(`✔ saved session: ${p.key} (${role})`);
  });
}
