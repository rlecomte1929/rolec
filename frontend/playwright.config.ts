import { defineConfig, devices } from '@playwright/test';
import { loadTestEnv } from './e2e/support/env';
import { PORTAL_ROLES, authFile } from './e2e/support/auth';

/**
 * Playwright config for ReloPass browser E2E — THREE modes.
 *
 * 1. PREVIEW mode (default; CI-gating). Builds the app and serves it with
 *    `vite preview` on :4173, then runs the deterministic, backend-free smoke
 *    specs (`e2e/smoke.*.spec.ts`): app boots, route guards redirect, the login
 *    UI works, and the core employee pages render against a MOCKED `/api`
 *    (page.route fixtures). No live backend → no flake → safe to gate PRs.
 *    This is also the shared preview+Playwright harness QG-9 (axe) and QG-13
 *    (Lighthouse) reuse. PR CI runs exactly this via `--project=chromium`.
 *
 * 2. LIVE mode (set `E2E_BASE_URL`, e.g. https://relopass.com). Runs the
 *    full suite INCLUDING `intake-persistence.spec.ts`, which needs the real
 *    FastAPI backend + seeded demo assignment (login via E2E_EMPLOYEE_EMAIL /
 *    E2E_EMPLOYEE_PASSWORD). In preview mode that live-only spec is skipped.
 *
 * 3. LIVE PORTALS (QG-AUTH; set `E2E_LIVE_PORTALS=1`, optional
 *    `E2E_PORTAL_BASE_URL`, default https://relopass.com). Signs in ONCE per role
 *    (`portals/auth.setup.ts` writes a Playwright storageState under
 *    playwright/.auth/), then the admin/hr/employee projects reuse that session —
 *    no password ever appears in a spec. Credentials come from frontend/.env.test
 *    (gitignored; template: .env.test.example). OFF by default and never selected
 *    by the PR gate; see docs/e2e-live-portals.md.
 *
 * Run locally: `npx playwright install chromium && npm run test:e2e` (preview),
 * `E2E_BASE_URL=https://relopass.com npm run test:e2e` (live), or
 * `npm run test:e2e:portals` (authenticated portals; needs .env.test).
 */

// Load frontend/.env.test if present (no-op in preview/PR CI). Must run before the
// portal projects read per-role credentials.
loadTestEnv();

const LIVE_TARGET = process.env.E2E_BASE_URL;
const RUN_PORTALS = process.env.E2E_LIVE_PORTALS === '1';
const PORTAL_BASE_URL = process.env.E2E_PORTAL_BASE_URL || 'https://relopass.com';

export default defineConfig({
  testDir: './e2e',
  // Test selection by mode. NOTE: this MUST live at the top level, not on a project —
  // a project-level `testIgnore` REPLACES this one rather than merging, which would
  // un-ignore intake-persistence in preview (a live-only spec) and fail the gate.
  //   • preview (default): skip the live-only spec AND the opt-in portal specs;
  //   • live (E2E_BASE_URL): run smoke + intake live, but never the portal specs;
  //   • portals (E2E_LIVE_PORTALS): nothing to globally ignore — each portal project
  //     selects its own file via testMatch, and the smoke specs match no project.
  testIgnore: RUN_PORTALS
    ? []
    : LIVE_TARGET
      ? ['**/portals/**']
      : ['**/intake-persistence.spec.ts', '**/portals/**'],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: RUN_PORTALS ? PORTAL_BASE_URL : LIVE_TARGET || 'http://localhost:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: RUN_PORTALS
    ? [
        // Sign in once per role and persist the session (the "door").
        { name: 'portal-setup', testMatch: /portals\/auth\.setup\.ts$/ },
        // One project per portal, reusing that role's stored session. Named so the
        // PR-gating `--project=chromium` run can never select them.
        ...PORTAL_ROLES.map((role) => ({
          name: `${role.toLowerCase()}-portal`,
          testMatch: new RegExp(`portals/${role.toLowerCase()}\\.portal\\.spec\\.ts$`),
          dependencies: ['portal-setup'],
          use: { ...devices['Desktop Chrome'], storageState: authFile(role) },
        })),
      ]
    : [
        // Deterministic default project. PR CI runs exactly this (--project=chromium).
        // Portal specs are excluded via the top-level testIgnore above (a project-level
        // testIgnore here would override it and un-ignore intake-persistence).
        { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
      ],
  // Only spin up a local preview in PREVIEW mode (skip for a live URL or live portals).
  webServer:
    LIVE_TARGET || RUN_PORTALS
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
