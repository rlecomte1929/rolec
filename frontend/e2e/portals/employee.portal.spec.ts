import { test } from '@playwright/test';
import { assertPortalReachable } from '../support/portal';

// Authenticated as EMPLOYEE via project storageState (portals/auth.setup.ts).
test.describe('employee portal · authenticated smoke', () => {
  test('employee lands inside /employee with a clean console', async ({ page }) => {
    await assertPortalReachable(page, { path: '/employee', inPortal: /\/employee/ });
    // TODO(QG-AUTH follow-up): open the roadmap and assert phases render.
  });
});
