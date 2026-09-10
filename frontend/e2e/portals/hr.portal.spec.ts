import { test } from '@playwright/test';
import { assertPortalReachable } from '../support/portal';

// Authenticated as HR via project storageState (portals/auth.setup.ts).
test.describe('hr portal · authenticated smoke', () => {
  test('hr lands inside /hr with a clean console', async ({ page }) => {
    await assertPortalReachable(page, { path: '/hr', inPortal: /\/hr/ });
    // TODO(QG-AUTH follow-up): open a case from the command center and assert it loads.
  });
});
