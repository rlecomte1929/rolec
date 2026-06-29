import { test, expect } from '@playwright/test';
import { assertLogicalPage, clarityScore, shot } from '../_helpers';

/** Admin persona (A1/A2 — admin@relopass.com via the `admin` project session). */

test('[PER-A1] admin console + suppliers + resources are logical', async ({ page }, info) => {
  for (const [route, label] of [
    ['/admin', '01_console'],
    ['/admin/suppliers', '02_suppliers'],
    ['/admin/resources', '03_resources'],
    ['/admin/companies', '04_companies'],
  ] as const) {
    await page.goto(route);
    const v = await assertLogicalPage(page, info, label);
    await shot(page, info, label);
    expect(v.signals, `${route} signals: ${v.signals}`).not.toContain('permanent-spinner(B10)');
  }
});

test('[VND-01] admin suppliers list — count + screenshot for real-company review', async ({ page }, info) => {
  await page.goto('/admin/suppliers');
  await page.waitForLoadState('networkidle').catch(() => {});
  await assertLogicalPage(page, info, 'suppliers');
  await shot(page, info, '01_suppliers_list');
  // Capture visible row text so the human/AI reviewer can spot dupes / neighborhood-rows / test rows.
  const rowsText = await page.locator('table tr, [role="row"], li').allInnerTexts().catch(() => []);
  await info.attach('supplier-rows', { body: JSON.stringify({ rows: rowsText.slice(0, 120) }, null, 2), contentType: 'application/json' });
});

test('[PER-A2] admin people/onboarding reachable (B2 invite note)', async ({ page }, info) => {
  await page.goto('/admin/people');
  const v = await assertLogicalPage(page, info, 'people');
  await shot(page, info, '01_people');
  // Look for an Add Person / invite control (B2 is the known invite gap).
  const add = page.getByRole('button', { name: /add person|new user|invite/i });
  await info.attach('onboarding', { body: JSON.stringify({ addControlPresent: await add.first().isVisible().catch(() => false), signals: v.signals }), contentType: 'application/json' });
});

test('[UX-CLARITY-admin] admin console clarity rubric', async ({ page }, info) => {
  await page.goto('/admin');
  const score = await clarityScore(page, info, 'admin-console');
  await info.attach('clarity', { body: JSON.stringify({ score }), contentType: 'application/json' });
});
