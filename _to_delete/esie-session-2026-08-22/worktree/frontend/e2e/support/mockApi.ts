import { Page } from '@playwright/test';

export type MockRoutes = Record<string, unknown>;

/**
 * QG-5b: mock the app's /api data layer for backend-free authed smoke.
 *
 * Registers a catch-all that 404s any /api request NOT explicitly listed (so a
 * missing mock is loud rather than a silent empty render), then one 200 + JSON
 * fulfilment per provided `glob → body`. Playwright matches the MOST-RECENTLY
 * registered route first, so the specific routes (added after the catch-all)
 * take precedence over it.
 *
 * Preview serves the SPA with a relative API base, so every call is `/api/...`
 * on the page origin — `**\/api\/**` globs intercept them all.
 */
export async function mockApi(page: Page, routes: MockRoutes): Promise<void> {
  await page.route('**/api/**', (route) =>
    route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'unmocked endpoint', url: route.request().url() }),
    }),
  );
  for (const [glob, body] of Object.entries(routes)) {
    await page.route(glob, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      }),
    );
  }
}
