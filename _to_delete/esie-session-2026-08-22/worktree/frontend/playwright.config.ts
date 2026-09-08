import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for ReloPass browser E2E — TWO modes (QG-5).
 *
 * 1. PREVIEW mode (default; CI-gating). Builds the app and serves it with
 *    `vite preview` on :4173, then runs the deterministic, backend-free smoke
 *    specs (`e2e/smoke.*.spec.ts`): app boots, route guards redirect, the login
 *    UI works, and the core employee pages render against a MOCKED `/api`
 *    (page.route fixtures). No live backend → no flake → safe to gate PRs.
 *    This is also the shared preview+Playwright harness QG-9 (axe) and QG-13
 *    (Lighthouse) reuse.
 *
 * 2. LIVE mode (set `E2E_BASE_URL`, e.g. https://relopass.com). Runs the
 *    full suite INCLUDING `intake-persistence.spec.ts`, which needs the real
 *    FastAPI backend + seeded demo assignment (login via E2E_EMPLOYEE_EMAIL /
 *    E2E_EMPLOYEE_PASSWORD). In preview mode that live-only spec is skipped.
 *
 * Run locally: `npx playwright install chromium && npm run test:e2e`
 * (preview), or `E2E_BASE_URL=https://relopass.com npm run test:e2e` (live).
 */
const LIVE_TARGET = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: './e2e',
  // The live-backend spec can't run against the mocked preview — skip it there.
  testIgnore: LIVE_TARGET ? [] : ['**/intake-persistence.spec.ts'],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: LIVE_TARGET || 'http://localhost:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Only spin up a local preview in PREVIEW mode (skip when targeting a live URL).
  webServer: LIVE_TARGET
    ? undefined
    : {
        command: 'npm run build && npm run preview',
        url: 'http://localhost:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
        // The build asserts VITE_SUPABASE_URL/ANON_KEY (config/env.ts) — inject
        // throwaway non-secret values so the app boots, and force a RELATIVE API
        // base so every /api call is interceptable by page.route (no real backend).
        env: {
          VITE_SUPABASE_URL: 'https://e2e.placeholder.supabase.co',
          // Spaces are intentional: this is never a real key (no Supabase call is
          // made in the no-backend smoke), and they keep the value below the
          // gitleaks generic-api-key heuristic (which matches contiguous tokens).
          VITE_SUPABASE_ANON_KEY: 'not a secret e2e placeholder',
          VITE_API_URL: '',
        },
      },
});
