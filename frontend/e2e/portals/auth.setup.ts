import { test as setup } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { PORTAL_ROLES, loginAs, authFile } from '../support/auth';

/**
 * The "door": sign in ONCE per role through the real login form and persist the
 * resulting session (relopass_token + role + Supabase session, all in localStorage)
 * to a Playwright storageState file. Every `*.portal.spec.ts` then reuses its role's
 * session via project `storageState` and never types a password.
 *
 * Sessions expire on their own (auto-close the door); rotating the throwaway
 * account's password force-closes it. Credentials come from frontend/.env.test —
 * see docs/e2e-live-portals.md.
 *
 * Only runs when E2E_LIVE_PORTALS=1 (playwright.config.ts adds the `portal-setup`
 * project only then), so it never touches preview / PR CI.
 */
for (const role of PORTAL_ROLES) {
  setup(`authenticate ${role}`, async ({ page }) => {
    const file = authFile(role);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    await loginAs(page, role);
    await page.context().storageState({ path: file });
  });
}
