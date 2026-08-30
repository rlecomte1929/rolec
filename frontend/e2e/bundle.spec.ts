/**
 * QG-13 · anonymous visitors must not download the auth SDK.
 *
 * @supabase/supabase-js is its own 57 kB (gzipped) chunk, and it used to be a STATIC
 * dependency of the entry bundle — so Vite emitted a <link rel="modulepreload"> for it on
 * every prerendered marketing page and every visitor fetched it before they had any
 * opportunity to log in.
 *
 * Five eager import chains put it there (FeatureFlagProvider, BookDemoModal → demoBooking,
 * client.ts → supabaseAuth, AppShell → rpc, and a dev-only debug page that was imported
 * statically). Each is now a dynamic import inside the async function that needs it.
 *
 * This asserts the OUTCOME rather than the import style, because the import style is easy
 * to regress by accident: one `import { supabase } from '../api/supabase'` at the top of
 * any eagerly-reachable module puts the whole chunk back.
 */
import { test, expect } from '@playwright/test';

const MARKETING_ROUTES = ['/', '/platform', '/why', '/how-it-works'];

test.describe('QG-13 · marketing pages do not ship the auth SDK', () => {
  for (const route of MARKETING_ROUTES) {
    test(`${route} neither preloads nor fetches supabase-vendor`, async ({ page }) => {
      const fetched: string[] = [];
      page.on('request', (r) => {
        if (/supabase-vendor/.test(r.url())) fetched.push(r.url());
      });

      await page.goto(route);
      await page.locator('#root *').first().waitFor({ timeout: 10_000 }).catch(() => {});

      const preloads = await page.evaluate(() =>
        Array.from(document.querySelectorAll('link[rel="modulepreload"]'))
          .map((l) => (l as HTMLLinkElement).href)
          .filter((h) => /supabase-vendor/.test(h)),
      );

      expect(preloads, `${route} preloads the auth SDK`).toEqual([]);
      expect(fetched, `${route} downloads the auth SDK`).toEqual([]);
    });
  }
});
