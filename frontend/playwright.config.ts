import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for ReloPass browser E2E.
 *
 * Targets a LIVE deployment (default prod relopass.com) rather than spinning up
 * a local stack — the intake-persistence spec needs the real FastAPI backend +
 * a seeded demo assignment, which the live env already provides. Override the
 * target with E2E_BASE_URL / E2E_API_URL and the login with
 * E2E_EMPLOYEE_EMAIL / E2E_EMPLOYEE_PASSWORD.
 *
 * NOTE: this suite is intentionally NOT wired into CI (the repo's GitHub token
 * lacks `workflow` scope to add a job, and CI has no browser/live-env). The
 * CI-gated regression guard for the same behaviour lives in the vitest test
 * `src/features/platform-v2/intake/__tests__/intakePersistence.test.ts`.
 * Run locally with: `npx playwright install chromium && npm run test:e2e`.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 1,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'https://relopass.com',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
