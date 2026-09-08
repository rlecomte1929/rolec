import { test, expect } from '@playwright/test';
import { seedAuth } from './support/auth';
import { mockApi } from './support/mockApi';
import {
  overviewFixture as overview,
  intakeEnvelopeFixture as intakeEnvelope,
} from './support/fixtures';

/**
 * QG-5b · authed page smoke. "Logged in" via seeded localStorage (client-side
 * guards) with NO backend — page data is mocked via page.route fixtures that are
 * contract-checked against the TS-1 zod schemas (see
 * src/api/schemas/__tests__/e2eFixtures.test.ts). Proves the 3 core employee
 * pages render their data (not a white screen / login redirect).
 *
 * The route `:caseId` is the linked assignment_id from the overview fixture.
 */
const CASE_ID = 'asg-e2e-1';

test.describe('QG-5b · authed page smoke (mocked /api)', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page, 'EMPLOYEE');
  });

  test('dashboard renders a linked assignment row', async ({ page }) => {
    await mockApi(page, { '**/api/employee/assignments/overview': overview });
    await page.goto('/employee/dashboard');
    const row = page.locator('#employee-hub-linked-assignments li').first();
    await expect(row).toBeVisible();
    await expect(row).toContainText('Acme E2E GmbH');
  });

  test('intake page hydrates from the draft envelope', async ({ page }) => {
    await mockApi(page, {
      '**/api/employee/assignments/overview': overview,
      '**/api/employee/assignments/*/intake': intakeEnvelope,
      '**/api/employee/assignments/*/intake-progress': { ok: true },
      '**/api/employee/assignments/*/intake-draft': { ok: true },
    });
    await page.goto(`/employee/case/${CASE_ID}/intake`);
    await expect(page.getByRole('heading', { name: /detailed intake/i })).toBeVisible();
  });

  // TODO [QG-5b follow-up]: roadmap render. The page reads the full
  // RelocationPlanViewResponseDTO (summary + phases + tasks) which has no TS-1 zod
  // schema to guard a fixture against drift — add a roadmap boundary schema first,
  // then a fixture validated against it (so the mock can't silently diverge).
});
