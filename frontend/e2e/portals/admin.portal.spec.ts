import { test } from '@playwright/test';
import { assertPortalReachable } from '../support/portal';

// Authenticated as ADMIN via project storageState (portals/auth.setup.ts).
test.describe('admin portal · authenticated smoke', () => {
  test('admin lands inside /admin with a clean console', async ({ page }) => {
    await assertPortalReachable(page, { path: '/admin', inPortal: /\/admin/ });
    // TODO(QG-AUTH follow-up): open the Countries CMS and assert a row renders.
  });
});
