import { defineConfig, devices } from '@playwright/test';

/**
 * ReloPass v2.0 campaign — production (relopass.com).
 *
 * Auth model (storageState): the `setup` project logs each persona in ONCE
 * (reading passwords from env vars you set) and saves a session file under
 * playwright/.auth/<persona>.json. Every other project reuses its saved session,
 * so no test re-authenticates. See README.md for the env vars + run order.
 */
const RUNID = process.env.RUNID || '20260628T221441Z';
const ARTIFACTS = `test-artifacts/${RUNID}`;

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,           // production: keep ordered + gentle
  workers: 1,                     // one session at a time; avoid hammering prod
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: `${ARTIFACTS}/_html-report`, open: 'never' }],
    ['json', { outputFile: `${ARTIFACTS}/_results.json` }],
  ],
  use: {
    baseURL: 'https://relopass.com',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    screenshot: 'on',             // every test keeps screenshots (evidence)
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1440, height: 900 },
  },
  outputDir: `${ARTIFACTS}/_test-results`,

  projects: [
    // Harness self-test (no auth, no network — setContent only). Locks the
    // assertLogicalPage B10 cold-start tolerance. Run with --project=selftest.
    { name: 'selftest', testDir: './tests/selftest', use: { ...devices['Desktop Chrome'] } },

    // ════ CI / UNATTENDED PATH (headless, self-provisioning) ═══════════════════
    // Register fresh is_test personas via API → playwright/.auth/{hr_a,emp_a,hr_b}.json.
    // No passwords typed; data is purgeable via `is_test=true`.
    { name: 'provision', testMatch: /provision\.setup\.ts/, retries: 1 },
    // Data-path readiness gate: after provisioning, wait for the real company-scoped
    // endpoints to be non-5xx (deeper than the shallow /health front-door). Writes
    // playwright/.auth/_ready.json; never hard-fails (drives the scorer --degraded).
    { name: 'readiness',  testMatch: /readiness\.setup\.ts/, dependencies: ['provision'], retries: 0 },
    // Core browser checks (graceful empty states, no B10/B13) on the fresh accounts.
    { name: 'core',       testDir: './tests/core',       dependencies: ['readiness'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/hr_a.json' } },
    // Write-flow lifecycle (create→assign→submit→message→RFQ) on the fresh pair.
    { name: 'write-flow', testDir: './tests/write-flow', dependencies: ['readiness'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/hr_a.json' } },
    // Deep journey: fill wizard → submit → poll roadmap → assert it RENDERS (employee session).
    { name: 'deep',       testDir: './tests/deep',       dependencies: ['readiness'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/emp_a.json' } },

    // ════ LOCAL / FULL-DEMO PATH (form login — needs PW_TESTCO / PW_DEMO) ══════
    // Authenticate every demo persona once → playwright/.auth/<persona>.json.
    { name: 'setup', testMatch: /auth\.setup\.ts/, retries: 2 },
    { name: 'admin',    testDir: './tests/admin',         dependencies: ['setup'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/admin.json' } },
    { name: 'employee', testDir: './tests/employee',      dependencies: ['setup'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/emp_tc.json' } },
    { name: 'hr',       testDir: './tests/hr',            dependencies: ['setup'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/hr_tc.json' } },
    { name: 'demo',          testDir: './tests/demo',          dependencies: ['setup'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/admin.json' } },
    { name: 'cross-company', testDir: './tests/cross-company', dependencies: ['setup'], use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/meridian_hr.json' } },
  ],
});
