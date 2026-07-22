import { test, expect, APIRequestContext } from '@playwright/test';
import { assertLogicalPage, shot, requestWithGatewayRetry } from '../_helpers';
import crypto from 'crypto';
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

/**
 * [AIQ-1685] Unlock a case's roadmap the way a real payment does. The roadmap is now
 * server-side paywalled (RELOPASS_ROADMAP_PAYWALL_ENABLED); a provisioned case is
 * access_tier='free', so GET /roadmap 402s until it is paid. Rather than bypass the
 * paywall, we drive the REAL fulfilment path: POST a locally-signed
 * `checkout.session.completed` at /api/stripe/webhook so the fulfilment brain flips
 * access_tier→'roadmap'. Signing mirrors scripts/stripe_test_mode_smoke.py
 * (Stripe-Signature: `t={ts},v1=HMAC_SHA256(secret, "{ts}." + rawBody)`), using Node's
 * crypto — no new dependency, no test-only bypass endpoint.
 *
 * Returns true only when the webhook reports applied|duplicate (the case is now paid).
 * Returns false when it cannot run — STRIPE_WEBHOOK_SECRET unset in CI, payments disabled
 * (503), an unresolved case_id (ignored), or a rejected signature — so the caller can skip
 * with a clear reason instead of mis-reporting a roadmap-generation regression.
 */
async function unlockRoadmapViaTestPayment(api: APIRequestContext, caseId: string): Promise<boolean> {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret || !caseId) return false;
  // A string body is sent verbatim by Playwright, so the bytes we sign are the bytes verified.
  const body = JSON.stringify({
    id: `evt_e2e_${crypto.randomUUID()}`,
    type: 'checkout.session.completed',
    data: {
      object: {
        id: 'cs_e2e', amount_total: 80000, currency: 'eur', payment_intent: 'pi_e2e',
        metadata: { case_id: caseId, tier: 'roadmap' },
      },
    },
  });
  const ts = Math.floor(Date.now() / 1000);
  const sig = crypto.createHmac('sha256', secret).update(`${ts}.${body}`).digest('hex');
  const r = await api.post(`${API}/api/stripe/webhook`, {
    headers: { 'Content-Type': 'application/json', 'Stripe-Signature': `t=${ts},v1=${sig}` },
    data: body,
  });
  if (!r.ok()) return false;
  const j = await r.json().catch(() => ({} as { status?: string }));
  return j?.status === 'applied' || j?.status === 'duplicate';
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
    // [AIQ-1685] The roadmap is server-side paywalled; a provisioned case is 'free' so GET
    // /roadmap 402s until paid. Complete a test-mode payment via the real webhook first so this
    // check validates GENERATION for a paid case (not the paywall). No-op if it can't run.
    const paid = await unlockRoadmapViaTestPayment(api, state.caseId!);
    let tracks = 0;
    let lastStatus = 0;
    for (let i = 0; i < 30; i++) {
      const r = await api.get(`${API}/api/cases/${state.caseId}/roadmap`, { headers: { Authorization: `Bearer ${emp}` } });
      lastStatus = r.status();
      if (r.ok()) {
        const j = await r.json().catch(() => ({}));
        tracks = Array.isArray(j.tracks) ? j.tracks.length : 0;
        if (tracks > 0) break;
      }
      await new Promise((res) => setTimeout(res, 2000));
    }
    await info.attach('roadmap-api', { body: JSON.stringify({ tracks, paid, lastStatus }), contentType: 'application/json' });
    // Paywalled (402) AND the test-mode payment couldn't complete → a payments-config gap
    // (STRIPE_WEBHOOK_SECRET not set in the E2E env, or payments disabled), NOT a roadmap
    // regression. Skip so the Sentinel doesn't file a false P0; a genuine generation break
    // (paid but still no tracks) still fails below.
    test.skip(lastStatus === 402 && !paid,
      'roadmap paywalled (402) and the test-mode unlock could not run — set STRIPE_WEBHOOK_SECRET in the E2E env (same value the backend verifies against)');
    state.roadmapReady = tracks > 0;
    expect(tracks, 'roadmap should have ≥1 track after submit').toBeGreaterThan(0);
  });

  test('[DEEP-ROADMAP-UX] employee roadmap page RENDERS (no spinner / "couldn\'t load")', async ({ page }, info) => {
    test.skip(!state.roadmapReady, 'no generated roadmap to render');
    // [AIQ-1637] The roadmap PAGE's spinner is gated by the plan-VIEW projection
    // (GET /api/relocation-plans/{case_id}/view → summary.total_tasks), NOT the /roadmap
    // tracks the sibling [DEEP-ROADMAP-API] polled — they materialise independently, so
    // tracks>0 does not mean the page will render immediately. The plan builds async
    // (~60–90s). Poll the page's ACTUAL gating endpoint to readiness first so the page
    // renders a built plan and its spinner clears fast; otherwise a cold-start/deploy-window
    // build gets caught mid-flight and mis-filed as a permanent-spinner(B10) (the false
    // regression this ticket chased).
    let planTasks = 0;
    for (let i = 0; i < 30; i++) {
      const r = await api.get(`${API}/api/relocation-plans/${state.caseId}/view`, { headers: { Authorization: `Bearer ${emp}` } });
      if (r.ok()) {
        const j = await r.json().catch(() => ({}));
        planTasks = j?.summary?.total_tasks ?? 0;
        if (planTasks > 0) break;
      }
      await new Promise((res) => setTimeout(res, 2000));
    }
    await info.attach('roadmap-plan-ready', { body: JSON.stringify({ planTasks }), contentType: 'application/json' });
    await page.goto(`/employee/case/${state.caseId}/roadmap`);
    await page.waitForTimeout(3000);
    // Belt-and-braces: size the permanent-spinner window to the documented ~60–90s build
    // window so a still-building roadmap never mis-files B10. A genuinely stuck spinner
    // (backend up, plan-view never returns tasks) still fails after the window. A ready
    // roadmap clears in <5s, so the common path stays fast.
    const v = await assertLogicalPage(page, info, 'deep-roadmap', { spinnerClearMs: 90000 });
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
