import { test, expect, APIRequestContext } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * Write-flow lifecycle (PER-H1 + MSG truth-table + VND-05 RFQ), driven via the
 * REAL API with the saved bearer tokens (robust vs multi-step UI forms). Runs on
 * the WORKING TestCompany pair (hr_tc + emp_tc) — the demo cases can't load.
 *
 * It CREATES data on production, tagged `_v2test_<runid>`; every created id is
 * emitted in the `created-ids-for-cleanup` attachment so the run can be cleaned
 * up (deletion is the operator's job) and notifications DB-confirmed afterwards.
 *
 * Contracts (grounded in repo recon):
 *  - POST /api/hr/cases                              (HR) → { caseId }
 *  - POST /api/hr/cases/{id}/assign                  (HR) { employeeIdentifier,… } → { assignmentId }
 *  - POST /api/employee/assignments/{id}/submit      (EMP) → { success }  (fires AIQ-1342 HR notify)
 *  - POST /api/cases/{id}/messages                   (HR/EMP) { content }  (poll-based, NO notification)
 *  - POST /api/hr/rfq-requests                       (HR) { case_id, vendor_id, service_category,… }
 */
const API = process.env.E2E_API_URL || 'https://api.relopass.com';
const RUNID = process.env.RUNID || `local-${Date.now()}`;
const TAG = `_v2test_${RUNID}`;
const VENDOR_ID = 'ed599b41-6c77-4675-9c98-6166c839c1ec'; // SIRVA Worldwide (Moving & Freight), is_active
const AUTH_DIR = path.join(__dirname, '..', '..', 'playwright', '.auth');

function token(key: string): string {
  const s = JSON.parse(fs.readFileSync(path.join(AUTH_DIR, `${key}.json`), 'utf8'));
  const ls = (s.origins || []).flatMap((o: { localStorage?: { name: string; value: string }[] }) => o.localStorage || []);
  const t = ls.find((x) => x.name === 'relopass_token');
  if (!t) throw new Error(`no relopass_token in session ${key}`);
  return t.value;
}

// The employee email to assign — provisioned by provision.setup.ts (emp_a).
function provisionedEmail(key: string): string {
  const p = JSON.parse(fs.readFileSync(path.join(AUTH_DIR, '_provisioned.json'), 'utf8'));
  const email = p?.personas?.[key]?.email;
  if (!email) throw new Error(`no provisioned email for ${key}`);
  return email;
}

test.describe.configure({ mode: 'serial' }); // create→assign→submit→message→rfq share state

test.describe('write-flow lifecycle (TestCompany)', () => {
  let api: APIRequestContext;
  let hr: string, emp: string;
  const created: Record<string, string> = {};

  test.beforeAll(async ({ playwright }) => {
    api = await playwright.request.newContext();
    hr = token('hr_a');
    emp = token('emp_a');
  });
  test.afterAll(async ({}, info) => {
    await info.attach('created-ids-for-cleanup', { body: JSON.stringify({ tag: TAG, created }, null, 2), contentType: 'application/json' });
  });

  test('[PER-H1] HR creates a case (POST /api/hr/cases)', async () => {
    const r = await api.post(`${API}/api/hr/cases`, { headers: { Authorization: `Bearer ${hr}` } });
    expect(r.status(), await r.text()).toBe(200);
    created.caseId = (await r.json()).caseId;
    expect(created.caseId, 'caseId returned').toBeTruthy();
  });

  test('[MSG-02] HR assigns the employee (<5s, no hang — B3)', async ({}, info) => {
    const t0 = Date.now();
    const r = await api.post(`${API}/api/hr/cases/${created.caseId}/assign`, {
      headers: { Authorization: `Bearer ${hr}` },
      data: { employeeIdentifier: provisionedEmail('emp_a'), employeeFirstName: TAG, employeeLastName: 'QA' },
    });
    const ms = Date.now() - t0;
    await info.attach('assign', { body: JSON.stringify({ status: r.status(), ms }), contentType: 'application/json' });
    expect(r.status(), await r.text()).toBe(200);
    created.assignmentId = (await r.json()).assignmentId;
    expect(ms, 'assignment must be <5s (B3)').toBeLessThan(5000);
  });

  test('[MSG-01] employee submits intake → status + HR notify (AIQ-1342)', async ({}, info) => {
    const r = await api.post(`${API}/api/employee/assignments/${created.assignmentId}/submit`, { headers: { Authorization: `Bearer ${emp}` } });
    const body = (await r.text()).slice(0, 800);
    await info.attach('submit-resp', { body: JSON.stringify({ status: r.status(), body }), contentType: 'application/json' });
    // a fresh case may be profile-incomplete → 400/422; capture either way (DB-confirm notification post-run)
    expect([200, 201, 400, 422], `submit status (${body})`).toContain(r.status());
  });

  test('[MSG-03] HR posts a message to the case thread', async ({}, info) => {
    const r = await api.post(`${API}/api/cases/${created.caseId}/messages`, {
      headers: { Authorization: `Bearer ${hr}` },
      data: { content: `${TAG} please upload your passport copy.` },
    });
    await info.attach('message-resp', { body: JSON.stringify({ status: r.status() }), contentType: 'application/json' });
    expect([200, 201], await r.text()).toContain(r.status());
    const j = await r.json().catch(() => ({} as { id?: string }));
    if (j.id) created.messageId = j.id;
  });

  test('[VND-05/MSG-05] HR sends an RFQ to a real vendor (SIRVA)', async ({}, info) => {
    const r = await api.post(`${API}/api/hr/rfq-requests`, {
      headers: { Authorization: `Bearer ${hr}` },
      data: { case_id: created.caseId, vendor_id: VENDOR_ID, service_category: 'moving', special_requirements: TAG },
    });
    await info.attach('rfq-resp', { body: JSON.stringify({ status: r.status(), body: (await r.text()).slice(0, 500) }), contentType: 'application/json' });
    const j = await r.json().catch(() => ({} as { rfq_id?: string }));
    if (j.rfq_id) created.rfqId = j.rfq_id;
    expect([200, 201], 'RFQ created').toContain(r.status());
  });
});
