/**
 * QG-12 · no duplicate requests for values that cannot change mid-session.
 *
 * Two bugs from the qa.replay.io sweep, both of which needed the RIGHT route to observe.
 * My first attempt counted requests on `/` and `/auth` and saw nothing — neither route
 * mounts ChangelogBell (it lives in AppShell, which only renders on authenticated pages),
 * and get-feature-flags returns early unless an identity is present, which `seedAuth`
 * supplies. A test on the wrong route reports zero and looks like a pass.
 *
 * Note this runs against a PRODUCTION build via `vite preview`, where StrictMode does not
 * double-invoke effects — so any duplicate counted here is a real one.
 */
import { test, expect, type Page } from '@playwright/test';
import { seedAuth } from './support/auth';
import { mockApi } from './support/mockApi';
import { overviewFixture as overview, intakeEnvelopeFixture as intakeEnvelope } from './support/fixtures';

const CASE_ID = 'asg-e2e-1';

/** Collect every request whose URL matches, mirroring trackNavigations in welcome.persistence.spec.ts. */
function trackRequests(page: Page, pattern: RegExp): { urls: string[] } {
  const urls: string[] = [];
  page.on('request', (r) => {
    if (pattern.test(r.url())) urls.push(r.url());
  });
  return { urls };
}

test.describe('QG-12 · request de-duplication', () => {
  test('changelog.json is fetched once per session, not once per navigation', async ({ page }) => {
    const seen = trackRequests(page, /\/changelog\.json/);
    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {
      '**/api/employee/assignments/overview': overview,
      '**/api/employee/assignments/*/intake': intakeEnvelope,
      '**/api/employee/assignments/*/intake-progress': { ok: true },
      '**/api/employee/assignments/*/intake-draft': { ok: true },
      '**/api/public/track': { ok: true },
    });

    await page.goto('/employee/dashboard');
    await expect(page.locator('#employee-hub-linked-assignments li').first()).toBeVisible();
    expect(seen.urls.length, 'one fetch on first mount').toBe(1);

    // A CLIENT-SIDE navigation, not page.goto — AppShell is rendered per-page rather than
    // as a router layout, so React Router unmounts and remounts it (and ChangelogBell with
    // it) on every route change. A second goto would be a full reload and prove nothing.
    await page.getByRole('link', { name: /intake form/i }).click();
    await expect(page.getByRole('heading', { name: /detailed intake/i })).toBeVisible();

    expect(seen.urls.length, `refetched on navigation: ${seen.urls.length} requests`).toBe(1);
  });

  test('get-feature-flags is invoked once per page load', async ({ page }) => {
    const seen = trackRequests(page, /\/functions\/v1\/get-feature-flags/);
    await page.route('**/functions/v1/get-feature-flags', (r) =>
      r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ flags: {} }) }));

    await seedAuth(page, 'EMPLOYEE');
    await mockApi(page, {
      '**/api/employee/assignments/overview': overview,
      '**/api/public/track': { ok: true },
    });

    await page.goto('/employee/dashboard');
    await expect(page.locator('#employee-hub-linked-assignments li').first()).toBeVisible();
    await page.waitForTimeout(1000); // let onAuthStateChange settle

    // getSession() and onAuthStateChange's INITIAL_SESSION resolve the SAME identity, so
    // the second call was pure duplication — and this one is a Supabase Edge Function, so
    // it costs invocation quota as well as latency.
    expect(seen.urls.length, `invoked ${seen.urls.length}x for one identity`).toBe(1);
  });
});
