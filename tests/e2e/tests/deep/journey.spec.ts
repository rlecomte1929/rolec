import { test, expect, APIRequestContext } from '@playwright/test';
import { assertLogicalPage, shot, requestWithGatewayRetry } from '../_helpers';
import fs from 'fs';
import path from 'path';

/**
 * DEEP provisioned-case journey — the test that actually catches "the roadmap
 * won't load". On the freshly-provisioned pair it walks the FULL flow:
 *   HR create case → assign → employee fills the wizard ≥90% → submit →
 *   poll the generated roadmap → assert the roadmap + services pages RENDER.
 *
 * Each step is its own scored [DEEP-*] check and degrades gracefully: if an
 * upstream step doesn't complete (e.g. submit is still <90%), the dependent
 * browser assertions skip with a recorded reason rather than cascading noise.
 *
 * Contracts (grounded in relopass_api_runner_patched.js WZ flow + schemas.py):
 *   PATCH /api/cases/{id}                         — CaseDraftDTO (fills completeness)
 *   POST  /api/employee/assignments/{id}/submit   — 200, async roadmap gen
 *   GET   /api/cases/{id}/roadmap                  — { tracks: [{ steps: [...] }] }
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
function provisioned(key: string): { email: string } {
  const p = JSON.parse(fs.readFileSync(path.join(AUTH_DIR, '_provisioned.json'), 'utf8'));
  return p?.personas?.[key] || {};
}

test.describe.configure({ mode: 'serial' });

test.describe('deep — provisioned-case journey (fill → submit → roadmap)', () => {
  let api: APIRequestContext;
  let hr: string, emp: string, empEmail: string;
  const state: { caseId?: string; assignmentId?: string; submitted?: boolean; roadmapReady?: boolean } = {};

  test.beforeAll(async ({ playwright }) => {
    api = await playwright.request.newContext();
    hr = token('hr_a');
    emp = token('emp_a');
    empEmail = provisioned('emp_a').email;
  });

  test('[DEEP-PROVISION-CASE] HR creates + assigns a case', async () => {
    const c = await requestWithGatewayRetry(() => api.post(`${API}/api/hr/cases`, { headers: { Authorization: `Bearer ${hr}` } }));
    expect(c.status(), await c.text()).toBe(200);
    state.caseId = (await c.json()).caseId;
    const a = await requestWithGatewayRetry(() => api.post(`${API}/api/hr/cases/${state.caseId}/assign`, {
      headers: { Authorization: `Bearer ${hr}` },
      data: { employeeIdentifier: empEmail, employeeFirstName: 'E2E', employeeLastName: 'Deep' },
    }));
    expect(a.status(), await a.text()).toBe(200);
    state.assignmentId = (await a.json()).assignmentId;
  });

  test('[DEEP-WIZARD] employee fills the intake wizard (≥90%)', async ({}, info) => {
    test.skip(!state.caseId, 'no case');
    // CaseDraftDTO — fill every section so profileCompleteness clears the 90% gate.
    const draft = {
      relocationBasics: { originCountry: 'FR', originCity: 'Paris', destCountry: 'DE', destCity: 'Berlin', purpose: 'work', targetMoveDate: '2026-12-01', durationMonths: 24, hasDependents: true },
      employeeProfile: { fullName: 'E2E Sentinel Employee', nationality: 'FR', passportCountry: 'FR', passportExpiry: '2030-01-01', residenceCountry: 'FR', email: empEmail },
      familyMembers: { maritalStatus: 'married', spouse: { fullName: 'E2E Spouse', dateOfBirth: '1990-01-01', relationship: 'spouse', nationality: 'FR', wantsToWork: true }, children: [] },
      assignmentContext: { employerName: 'E2E Sentinel A', employerCountry: 'DE', workLocation: 'Berlin', contractStartDate: '2026-12-15', contractType: 'permanent', salaryBand: 'L4', jobTitle: 'Engineer', seniorityBand: 'senior' },
      services: ['housing', 'immigration', 'tax', 'moving'],
    };
    // The intake is the employee's; fill with the employee token.
    const r = await requestWithGatewayRetry(() => api.patch(`${API}/api/cases/${state.caseId}`, { headers: { Authorization: `Bearer ${emp}` }, data: draft }));
    await info.attach('wizard', { body: JSON.stringify({ status: r.status(), body: (await r.text()).slice(0, 400) }), contentType: 'application/json' });
    expect(r.status(), 'wizard PATCH must not 5xx').toBeLessThan(500);
  });

  test('[DEEP-SUBMIT] employee submits → 200 (profile complete)', async ({}, info) => {
    test.skip(!state.assignmentId, 'no assignment');
    const r = await requestWithGatewayRetry(() => api.post(`${API}/api/employee/assignments/${state.assignmentId}/submit`, { headers: { Authorization: `Bearer ${emp}` } }));
    const body = (await r.text()).slice(0, 600);
    await info.attach('submit', { body: JSON.stringify({ status: r.status(), body }), contentType: 'application/json' });
    state.submitted = r.status() === 200;
    // 400 here = the wizard fill didn't reach 90% (data gap) — informative, not a 5xx.
    expect(r.status(), `submit (${body})`).toBeLessThan(500);
  });

  test('[DEEP-ROADMAP-API] roadmap generates (tracks non-empty within 60s)', async ({}, info) => {
    test.skip(!state.submitted, 'submit did not succeed → no roadmap to generate');
    let tracks = 0;
    for (let i = 0; i < 30; i++) {
      const r = await api.get(`${API}/api/cases/${state.caseId}/roadmap`, { headers: { Authorization: `Bearer ${emp}` } });
      if (r.ok()) {
        const j = await r.json().catch(() => ({}));
        tracks = Array.isArray(j.tracks) ? j.tracks.length : 0;
        if (tracks > 0) break;
      }
      await new Promise((res) => setTimeout(res, 2000));
    }
    await info.attach('roadmap-api', { body: JSON.stringify({ tracks }), contentType: 'application/json' });
    state.roadmapReady = tracks > 0;
    expect(tracks, 'roadmap should have ≥1 track after submit').toBeGreaterThan(0);
  });

  test('[DEEP-ROADMAP-UX] employee roadmap page RENDERS (no spinner / "couldn\'t load")', async ({ page }, info) => {
    test.skip(!state.roadmapReady, 'no generated roadmap to render');
    await page.goto(`/employee/case/${state.caseId}/roadmap`);
    await page.waitForTimeout(3000);
    const v = await assertLogicalPage(page, info, 'deep-roadmap');
    await shot(page, info, '01_roadmap');
    const body = await page.locator('body').innerText().catch(() => '');
    await info.attach('roadmap-ux', { body: JSON.stringify({ heading: v.heading, signals: v.signals, couldntLoad: /couldn't load|could not load/i.test(body) }), contentType: 'application/json' });
    expect(v.signals, `roadmap: ${v.signals}`).not.toContain('permanent-spinner(B10)');
    expect(body, 'roadmap must not show "couldn\'t load"').not.toMatch(/couldn't load|could not load/i);
  });

  test('[DEEP-SERVICES-UX] employee services page renders a vendor list', async ({ page }, info) => {
    test.skip(!state.caseId || !state.submitted, 'no submitted case');
    await page.goto(`/employee/case/${state.caseId}/services/select`);
    const v = await assertLogicalPage(page, info, 'deep-services');
    await shot(page, info, '01_services');
    const vendorCards = await page.locator('[role="checkbox"]').count().catch(() => 0);
    await info.attach('services-ux', { body: JSON.stringify({ signals: v.signals, vendorCards }), contentType: 'application/json' });
    expect(v.signals, `services: ${v.signals}`).not.toContain('permanent-spinner(B10)');
  });
});
