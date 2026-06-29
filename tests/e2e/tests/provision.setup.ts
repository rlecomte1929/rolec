import { test as setup, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * HEADLESS PROVISIONING (CI auth path) — replaces the form-login auth.setup.ts.
 *
 * Registers fresh, throwaway personas via POST /api/auth/register (no UI, no
 * stored passwords), captures each session token, and writes it directly into
 * playwright/.auth/<key>.json as storageState. Downstream browser projects reuse
 * those sessions exactly like the form-login path did.
 *
 * Why this is safe + self-cleaning:
 *  - Emails end in @testco.com → the backend auto-sets `is_test = true` on the
 *    company + profile (migration 2026-06-29), so `scripts/e2e_purge.py` can wipe
 *    every row this run created with `WHERE is_test = true` — and that predicate
 *    deliberately does NOT match the @testcompany.com / @*-demo.com demo tenants.
 *  - The one password comes from the RELOPASS_E2E_PASSWORD env var (a CI secret);
 *    nothing is hardcoded and no password is ever typed into a form.
 *
 * Registering an HR with `company_name` auto-creates + links the company and
 * returns user.company (the B18 guard) — no company needs to exist first.
 */
const API = process.env.E2E_API_URL || 'https://api.relopass.com';
const APP = process.env.E2E_APP_URL || 'https://relopass.com';
const PW = process.env.RELOPASS_E2E_PASSWORD;

// short, unique, filesystem-safe tag → unique is_test emails per run
const TAG = (process.env.RUNID || String(Date.now())).replace(/[^a-z0-9]/gi, '').toLowerCase().slice(-12);
const AUTH_DIR = path.join(__dirname, '..', 'playwright', '.auth');

type Role = 'HR' | 'EMPLOYEE';
interface Spec { key: string; role: Role; company_name?: string }
interface Provisioned { key: string; email: string; token: string; userId: string; role: Role; company: string | null }

// HR-A (+ company A) and Employee-A run the core lifecycle; HR-B (+ company B)
// is the second tenant for the cross-company RLS check.
const SPECS: Spec[] = [
  { key: 'hr_a', role: 'HR', company_name: `E2E Sentinel A ${TAG} (Seed)` },
  { key: 'emp_a', role: 'EMPLOYEE' },
  { key: 'hr_b', role: 'HR', company_name: `E2E Sentinel B ${TAG} (Seed)` },
];

setup('provision is_test personas via API', async ({ request }) => {
  setup.skip(!PW, 'RELOPASS_E2E_PASSWORD not set — cannot provision (set it to run the headless path)');
  setup.setTimeout(240_000); // a 429 retry can wait ~60s; allow headroom for up to 3 registrations
  fs.mkdirSync(AUTH_DIR, { recursive: true });

  // Registration is rate-limited; on 429 honor retry_after and retry (the API-smoke
  // layer + these 3 registrations can otherwise blow the per-window budget).
  async function registerWithRetry(data: Record<string, string>, key: string) {
    for (let attempt = 1; attempt <= 3; attempt++) {
      const resp = await request.post(`${API}/api/auth/register`, { data });
      if (resp.status() !== 429) return resp;
      let retryAfter = 60;
      try { retryAfter = (JSON.parse(await resp.text()).retry_after as number) || 60; } catch { /* default */ }
      console.log(`  ${key}: 429 rate-limited — waiting ${retryAfter + 3}s (attempt ${attempt}/3)`);
      await new Promise((res) => setTimeout(res, (retryAfter + 3) * 1000));
    }
    return request.post(`${API}/api/auth/register`, { data });
  }

  const provisioned: Record<string, Provisioned> = {};
  for (const s of SPECS) {
    const email = `e2e_${s.key}_${TAG}@testco.com`;
    const data: Record<string, string> = { email, password: PW!, name: `E2E ${s.key} ${TAG}`, role: s.role };
    if (s.company_name) data.company_name = s.company_name;

    const r = await registerWithRetry(data, s.key);
    expect(r.status(), `register ${s.key} → ${await r.text()}`).toBeLessThan(300);
    const j = await r.json();
    const user = j.user || {};
    expect(j.token, `token for ${s.key}`).toBeTruthy();
    // Fresh HR must come back company-linked (B18 / AIQ-542 regression guard).
    if (s.role === 'HR') {
      expect(user.company, `${s.key}: a fresh HR must be auto-linked to a company (B18)`).toBeTruthy();
    }

    const localStorageItems = [
      { name: 'relopass_token', value: String(j.token) },
      { name: 'relopass_role', value: s.role },
      { name: 'relopass_user_id', value: String(user.id || '') },
      { name: 'relopass_email', value: email },
      { name: 'relopass_username', value: String(user.username || email) },
      { name: 'relopass_name', value: String(user.name || email) },
    ];
    const state = { cookies: [], origins: [{ origin: APP, localStorage: localStorageItems }] };
    fs.writeFileSync(path.join(AUTH_DIR, `${s.key}.json`), JSON.stringify(state, null, 2));

    provisioned[s.key] = { key: s.key, email, token: String(j.token), userId: String(user.id || ''), role: s.role, company: user.company || null };
    console.log(`✔ provisioned ${s.key} (${s.role}) ${email} company=${user.company || '-'}`);

    // gentle pacing: consecutive registrations can trip the auth rate limiter
    await new Promise((res) => setTimeout(res, 2500));
  }

  // Shared identities for downstream specs (e.g. write-flow assigns emp_a by email).
  fs.writeFileSync(
    path.join(AUTH_DIR, '_provisioned.json'),
    JSON.stringify({ tag: TAG, runid: process.env.RUNID || `local-${TAG}`, personas: provisioned }, null, 2),
  );
});
