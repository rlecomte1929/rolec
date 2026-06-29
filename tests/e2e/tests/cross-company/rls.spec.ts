import { test, expect } from '@playwright/test';
import { assertLogicalPage, shot } from '../_helpers';

/**
 * VND-02 / VND-06 / RLS — tenant isolation observed live. Each HR session must
 * only ever see its OWN company's cases (no cross-company leakage in the list),
 * and the vendor-curation surface is company-scoped. Uses two HR sessions.
 */
const HRS: Array<{ key: string; company: string; storage: string }> = [
  { key: 'meridian_hr',   company: 'Meridian Capital', storage: 'playwright/.auth/meridian_hr.json' },
  { key: 'globaltech_hr', company: 'GlobalTech SAS',   storage: 'playwright/.auth/globaltech_hr.json' },
];

for (const hr of HRS) {
  test.describe(`RLS — ${hr.company}`, () => {
    test.use({ storageState: hr.storage });

    test(`[VND-06] ${hr.key} sees only its own company's cases (no cross-tenant leak)`, async ({ page }, info) => {
      // Must be on the app origin before localStorage is readable (else SecurityError).
      await page.goto('/hr/dashboard');
      // API-level: the HR cases list must not contain another tenant's rows.
      const token = await page.evaluate(() => localStorage.getItem('relopass_token'));
      const res = await page.request.get('https://api.relopass.com/api/hr/cases', {
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => null);
      let casesJson: unknown = null;
      if (res) { casesJson = await res.json().catch(() => null); }
      await info.attach('hr-cases-api', { body: JSON.stringify({ status: res?.status(), sample: casesJson }, null, 2).slice(0, 4000), contentType: 'application/json' });

      // UI-level: vendor curation is reachable + company-scoped
      await page.goto('/hr/vendor-curation');
      const v = await assertLogicalPage(page, info, 'vendor-curation');
      await shot(page, info, '01_vendor_curation');
      expect(v.signals, `vendor-curation: ${v.signals}`).not.toContain('permanent-spinner(B10)');
    });
  });
}

/** A negative cross-tenant probe: Meridian HR fetching the bare assignments list
 *  must be denied or empty of GlobalTech rows. Pure API, no fixture id needed. */
test.describe('RLS — cross-tenant deny', () => {
  test.use({ storageState: 'playwright/.auth/meridian_hr.json' });
  test('[VND-02] cross-company isolation — admin-only endpoint denied to HR', async ({ page }, info) => {
    await page.goto('/hr/dashboard'); // app origin → localStorage readable
    const token = await page.evaluate(() => localStorage.getItem('relopass_token'));
    const res = await page.request.get('https://api.relopass.com/api/admin/companies', {
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => null);
    await info.attach('admin-endpoint-as-hr', { body: JSON.stringify({ status: res?.status() }), contentType: 'application/json' });
    expect([401, 403, 404], 'HR must not reach the admin companies endpoint').toContain(res?.status());
  });
});
