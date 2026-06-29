import { test, expect } from '@playwright/test';
import { assertLogicalPage, shot, openFirstEmployeeCase } from '../_helpers';

/**
 * DEMO-C1..C5 dress rehearsal, observed per demo employee. Each demo company's
 * employee is opened with its own saved session; we capture the destination, the
 * roadmap (immigration render), and the vendor list — the per-corridor
 * demo-readiness evidence. (Corridor→company mapping is resolved in the report
 * from the captured destination.)
 */
const EMPLOYEES: Array<{ key: string; label: string; storage: string }> = [
  { key: 'emp_tc',         label: 'DEMO-TestCompany', storage: 'playwright/.auth/emp_tc.json' },
  { key: 'globaltech_emp', label: 'DEMO-GlobalTech',  storage: 'playwright/.auth/globaltech_emp.json' },
  { key: 'meridian_emp',   label: 'DEMO-Meridian',    storage: 'playwright/.auth/meridian_emp.json' },
  { key: 'nexora_emp',     label: 'DEMO-Nexora',      storage: 'playwright/.auth/nexora_emp.json' },
];

for (const emp of EMPLOYEES) {
  test.describe(emp.label, () => {
    test.use({ storageState: emp.storage });

    test(`[${emp.label}] journey: case → roadmap(immigration) → vendors`, async ({ page }, info) => {
      const caseId = await openFirstEmployeeCase(page);
      await shot(page, info, '01_dashboard');
      expect(caseId, `${emp.key}: a case should exist`).toBeTruthy();
      if (!caseId) return;

      // destination (corridor) signal from the case header / roadmap
      await page.goto(`/employee/case/${caseId}/roadmap`);
      await page.waitForTimeout(3000);
      const rv = await assertLogicalPage(page, info, 'roadmap');
      await shot(page, info, '02_roadmap');
      const body = await page.locator('body').innerText().catch(() => '');
      const immigrationPresent = /visa|permit|registration|residence|immigration|anmeldung|bsn|employment pass|emirates id/i.test(body);

      // vendors
      await page.goto(`/employee/case/${caseId}/services/select`);
      const sv = await assertLogicalPage(page, info, 'services');
      await shot(page, info, '03_services');
      const vendorCards = await page.locator('[role="checkbox"]').count().catch(() => 0);

      await info.attach('corridor-readiness', {
        body: JSON.stringify({
          employee: emp.key, caseId,
          roadmapHeading: rv.heading, roadmapSignals: rv.signals,
          immigrationContentPresent: immigrationPresent,
          servicesSignals: sv.signals, vendorCards,
        }, null, 2),
        contentType: 'application/json',
      });
    });
  });
}
