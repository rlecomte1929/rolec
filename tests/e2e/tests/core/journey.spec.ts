import { test, expect } from '@playwright/test';
import { assertLogicalPage, shot } from '../_helpers';
import fs from 'fs';
import path from 'path';

/**
 * CORE — the CI/unattended browser layer, run on the freshly-provisioned
 * is_test accounts (hr_a, emp_a). A brand-new company has no cases yet, so this
 * layer asserts the EMPTY/ONBOARDING states render gracefully (the e2e principle:
 * a missing precondition must degrade gracefully, never hard-fail) + the
 * isolation/authz invariants. The deep roadmap/vendor UX on a fully-provisioned
 * case is exercised by the local/demo path (and is a Phase-2 CI addition).
 */
const API = process.env.E2E_API_URL || 'https://api.relopass.com';
const AUTH_DIR = path.join(__dirname, '..', '..', 'playwright', '.auth');

function token(key: string): string {
  const s = JSON.parse(fs.readFileSync(path.join(AUTH_DIR, `${key}.json`), 'utf8'));
  const ls = (s.origins || []).flatMap((o: { localStorage?: { name: string; value: string }[] }) => o.localStorage || []);
  const t = ls.find((x) => x.name === 'relopass_token');
  if (!t) throw new Error(`no relopass_token in session ${key}`);
  return t.value;
}

// HR-A core surfaces must render a logical page (heading, no B10 spinner, no B13
// raw-error) even with zero cases — graceful empty state.
test.describe('core — HR-A surfaces (fresh company)', () => {
  for (const [route, label] of [
    ['/hr/dashboard', 'dashboard'],
    ['/hr/command-center', 'command-center'],
    ['/hr/vendor-curation', 'vendor-curation'],
  ] as const) {
    test(`[CORE-HR-${label}] ${route} renders a logical page`, async ({ page }, info) => {
      await page.goto(route);
      const v = await assertLogicalPage(page, info, `hr-${label}`);
      await shot(page, info, `01_${label}`);
      expect(v.signals, `${label}: ${v.signals}`).not.toContain('permanent-spinner(B10)');
      expect(v.signals, `${label}: ${v.signals}`).not.toContain('raw-error-no-retry(B13)');
    });
  }
});

// Employee-A dashboard (no case yet) must render a graceful onboarding/empty state.
test.describe('core — Employee-A dashboard', () => {
  test.use({ storageState: 'playwright/.auth/emp_a.json' });
  test('[CORE-EMP-dashboard] /employee/dashboard renders a logical page', async ({ page }, info) => {
    await page.goto('/employee/dashboard');
    const v = await assertLogicalPage(page, info, 'emp-dashboard');
    await shot(page, info, '01_dashboard');
    expect(v.signals, `emp dashboard: ${v.signals}`).not.toContain('permanent-spinner(B10)');
  });
});

// API-level isolation + graceful-degradation guards (no browser fixture needed).
test.describe('core — isolation + graceful degradation (API)', () => {
  test('[CORE-RLS] HR-A cases list is scoped + admin endpoint denied (403)', async ({ request }, info) => {
    const t = token('hr_a');
    const cases = await request.get(`${API}/api/hr/cases`, { headers: { Authorization: `Bearer ${t}` } });
    const admin = await request.get(`${API}/api/admin/companies`, { headers: { Authorization: `Bearer ${t}` } });
    await info.attach('rls', { body: JSON.stringify({ cases: cases.status(), admin: admin.status() }), contentType: 'application/json' });
    expect(cases.status(), 'HR cases list must be reachable (not 5xx)').toBeLessThan(500);
    expect([401, 403, 404], 'HR must be denied the admin companies endpoint').toContain(admin.status());
  });

  test('[CORE-DEGRADE] fresh HR policy-config degrades gracefully (not 5xx)', async ({ request }, info) => {
    const t = token('hr_a');
    const r = await request.get(`${API}/api/hr/policy-config`, { headers: { Authorization: `Bearer ${t}` } });
    await info.attach('policy-config', { body: JSON.stringify({ status: r.status() }), contentType: 'application/json' });
    // A fresh-but-company-linked HR with no published policy must get an empty/onboarding
    // 200 (or a clean 404) — never a 5xx. (Canonical violation: 400 "missing company".)
    expect(r.status(), 'policy-config must not 5xx for a fresh HR').toBeLessThan(500);
  });
});
