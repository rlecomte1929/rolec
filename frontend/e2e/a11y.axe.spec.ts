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

  // AIQ · accent-as-text contrast. These two orientation routes render the brand teal
  // as body text and need no API at all, so they are the cheapest real coverage for the
  // accent cluster. color-contrast is enabled (since #2070), so this measures it.
  test('HR welcome page has no serious/critical a11y violations', async ({ page }) => {
    await seedAuth(page, 'HR');
    await page.goto('/hr/welcome');
    await expect(page.locator('#root *')).not.toHaveCount(0);
    await expectNoSeriousA11yViolations(page);
  });

  test('employee welcome page has no serious/critical a11y violations', async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
    await page.goto('/employee/welcome');
    await expect(page.locator('#root *')).not.toHaveCount(0);
    await expectNoSeriousA11yViolations(page);
  });

  // The admin tree was 0% measured until now, and the accent cluster is concentrated there
  // (7 of the 45 accent-carrying files). These four need NO mocking: every /api call falls
  // through mockApi's catch-all 404 and the page renders its empty state, which is a real
  // state an admin sees. That is enough to reach the shell chrome — where the "NEW" sidebar
  // badge sits on bg-accent-50 at 3.61:1, on EVERY one of these routes.
  for (const [route, label] of [
    ['/admin/test-drive', 'admin test-drive'],
    ['/admin/feedback', 'admin feedback'],
    ['/admin/content-review', 'admin content review'],
    ['/admin/users', 'admin users'],
  ] as const) {
    test(`${label} (${route}) has no serious/critical a11y violations`, async ({ page }) => {
      await seedAuth(page, 'ADMIN');
      await page.goto(route);
      await expect(page.locator('#root *')).not.toHaveCount(0);
      await expectNoSeriousA11yViolations(page);
    });
  }

  // The only route that renders AIRecommendationCard from mockable data. HrExceptionsPage
  // also renders it, but hardcodes aiInsight: undefined for server data, so it is
  // unreachable there; HrCaseSummary needs four endpoints. This needs one, and riskStatus
  // 'red' is what mounts the card. budget* fields mount the budget status line.
  test('HR command-center case detail has no serious/critical a11y violations', async ({ page }) => {
    await seedAuth(page, 'HR');
    await mockApi(page, {
      '**/api/hr/command-center/cases/*': {
        id: 'asg-e2e-1',
        caseId: 'case-e2e-1',
        employeeIdentifier: 'e2e@probe.test',
        destCountry: 'IE',
        destCity: 'Dublin',
        status: 'active',
        riskStatus: 'red',
        budgetLimit: 1000,
        budgetEstimated: 1500,
        tasksTotal: 4,
        tasksDone: 1,
        tasksOverdue: 2,
        phases: [{ phase: 'immigration', tasks: [{ title: 'Visa', status: 'overdue' }] }],
        events: [{ event_type: 'created', description: 'Case created', created_at: '2026-08-01T00:00:00Z' }],
      },
    });
    await page.goto('/hr/command-center/cases/asg-e2e-1');
    await expect(page.getByText('Budget overview')).toBeVisible();
    await expectNoSeriousA11yViolations(page);
  });
});
