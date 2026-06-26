import { test, expect } from '@playwright/test';
import { seedAuth } from './support/auth';
import { mockApi } from './support/mockApi';
import {
  overviewFixture as overview,
  intakeEnvelopeFixture as intakeEnvelope,
} from './support/fixtures';
import { expectNoSeriousA11yViolations } from './support/axe';

/**
 * QG-9 · runtime accessibility gate (AIQ-1182). Runs axe-core against the key
 * employee-facing pages served by the QG-5 `vite preview` harness (no live
 * backend; auth seeded + /api mocked) and FAILS on serious/critical violations
 * only. New spec → auto-picked up by the CI `e2e` job (gates frontend PRs).
 *
 * Roadmap is intentionally NOT covered yet — QG-5b left roadmap render as a
 * follow-up (no boundary fixture). Add it once that fixture lands.
 */
const CASE_ID = 'asg-e2e-1';

test.describe('QG-9 · runtime accessibility gate (axe — serious/critical only)', () => {
  test('landing page (/) has no serious/critical a11y violations', async ({ page }) => {
    await page.goto('/');
    // Settle: the React root must have rendered real content before we scan.
    await expect(page.locator('#root *')).not.toHaveCount(0);
    await expectNoSeriousA11yViolations(page);
  });

  test('login page (/auth) has no serious/critical a11y violations', async ({ page }) => {
    await page.goto('/auth');
    await expect(page.locator('#auth-login-identifier')).toBeVisible();
    await expectNoSeriousA11yViolations(page);
  });

  test('employee dashboard has no serious/critical a11y violations', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, { '**/api/employee/assignments/overview': overview });
    await page.goto('/employee/dashboard');
    await expect(page.locator('#employee-hub-linked-assignments li').first()).toBeVisible();
    await expectNoSeriousA11yViolations(page);
  });

  test('employee intake page has no serious/critical a11y violations', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {
      '**/api/employee/assignments/overview': overview,
      '**/api/employee/assignments/*/intake': intakeEnvelope,
      '**/api/employee/assignments/*/intake-progress': { ok: true },
      '**/api/employee/assignments/*/intake-draft': { ok: true },
    });
    await page.goto(`/employee/case/${CASE_ID}/intake`);
    await expect(page.getByRole('heading', { name: /detailed intake/i })).toBeVisible();
    await expectNoSeriousA11yViolations(page);
  });
});
