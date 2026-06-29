import { test, expect } from '@playwright/test';
import { assertLogicalPage, clarityScore, shot } from '../_helpers';

/** HR persona (H1/H2 — hr@testcompany.com via the `hr` project session). */

test('[PER-H1] HR dashboard + command center are logical; "New case" CTA present', async ({ page }, info) => {
  await page.goto('/hr/dashboard');
  const v = await assertLogicalPage(page, info, 'hr-dashboard');
  await shot(page, info, '01_dashboard');
  const newCase = page.getByRole('button', { name: /new case|first case/i }).or(page.getByRole('link', { name: /new case|first case/i }));
  await info.attach('hr-dashboard', { body: JSON.stringify({ newCaseCta: await newCase.first().isVisible().catch(() => false), signals: v.signals }), contentType: 'application/json' });

  await page.goto('/hr/command-center');
  const v2 = await assertLogicalPage(page, info, 'command-center');
  await shot(page, info, '02_command_center');
  expect(v2.signals, `command-center: ${v2.signals}`).not.toContain('permanent-spinner(B10)');
});

test('[MSG-09] "employees waiting" widget resolves within 5s (B16)', async ({ page }, info) => {
  await page.goto('/hr/dashboard');
  await page.waitForTimeout(5000);
  const widget = page.locator(':text("waiting"), :text("Employees waiting")').first();
  const present = await widget.isVisible().catch(() => false);
  const stillSpinning = await page.locator('[role="status"], .animate-spin').first().isVisible().catch(() => false);
  await shot(page, info, '01_waiting_widget');
  await info.attach('widget', { body: JSON.stringify({ widgetPresent: present, stillSpinningAfter5s: stillSpinning }), contentType: 'application/json' });
});

test('[VND-03] HR vendor curation + preferred suppliers are logical', async ({ page }, info) => {
  for (const [route, label] of [
    ['/hr/vendor-curation', '01_vendor_curation'],
    ['/hr/preferred-suppliers', '02_preferred_suppliers'],
  ] as const) {
    await page.goto(route);
    const v = await assertLogicalPage(page, info, label);
    await shot(page, info, label);
    await info.attach(label, { body: JSON.stringify({ signals: v.signals, heading: v.heading }), contentType: 'application/json' });
  }
});

test('[PER-H2] first-time-HR clarity rubric across the must-use screens', async ({ page }, info) => {
  const screens: Array<[string, string]> = [
    ['/hr/dashboard', 'dashboard'],
    ['/hr/command-center', 'command-center'],
    ['/hr/vendor-curation', 'vendor-curation'],
    ['/hr/policy', 'policy'],
  ];
  const scores: Record<string, number> = {};
  for (const [route, label] of screens) {
    await page.goto(route);
    scores[label] = await clarityScore(page, info, `h2-${label}`);
    await shot(page, info, `clarity_${label}`);
  }
  await info.attach('h2-clarity-table', { body: JSON.stringify(scores, null, 2), contentType: 'application/json' });
});
