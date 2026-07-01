import { test as setup } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * DATA-PATH READINESS GATE (Phase 3 of the deploy-tolerance hardening).
 *
 * The workflow's front-door `/health` probe is shallow liveness — it can be 200 while
 * the company-scoped data paths are still cold/erroring during a Render rolling-restart
 * (exactly the AIQ-1395 miss: /health 200 but the dashboard queries 5xx'd). This runs
 * AFTER provisioning (so it has a real hr_a token) and polls the ACTUAL data endpoints
 * the browser layer depends on until they're non-5xx, then records the verdict to
 * playwright/.auth/_ready.json for the scorer's degraded gate.
 *
 * It deliberately NEVER hard-fails: if the data path never warms, dependents still run
 * and self-classify their failures as environmental (Signal A), and the run is marked
 * INCONCLUSIVE via the `_ready.json {ready:false}` marker (`--degraded`) rather than
 * mass-SKIPPING (which would risk a vacuous green).
 */
const API = process.env.E2E_API_URL || 'https://api.relopass.com';
const AUTH_DIR = path.join(__dirname, '..', 'playwright', '.auth');
const ENDPOINTS = ['/api/hr/cases', '/api/hr/policy-config'];
const ATTEMPTS = 8;
const INTERVAL_MS = 10_000;

function hrToken(): string | null {
  try {
    const s = JSON.parse(fs.readFileSync(path.join(AUTH_DIR, 'hr_a.json'), 'utf8'));
    const ls = (s.origins || []).flatMap(
      (o: { localStorage?: { name: string; value: string }[] }) => o.localStorage || [],
    );
    return ls.find((x: { name: string }) => x.name === 'relopass_token')?.value || null;
  } catch {
    return null;
  }
}

setup('[READINESS] company data paths are warm', async ({ request }, info) => {
  setup.setTimeout((ATTEMPTS + 2) * INTERVAL_MS);
  const token = hrToken();
  let ready = false;
  let lastCodes: number[] = [];

  if (token) {
    for (let i = 0; i < ATTEMPTS; i++) {
      lastCodes = await Promise.all(
        ENDPOINTS.map((e) =>
          request
            .get(`${API}${e}`, { headers: { Authorization: `Bearer ${token}` }, timeout: 15_000 })
            .then((r) => r.status())
            .catch(() => 0),
        ),
      );
      // ready = every data endpoint answered non-5xx (0 = network error → not ready)
      if (lastCodes.every((c) => c > 0 && c < 500)) {
        ready = true;
        break;
      }
      if (i < ATTEMPTS - 1) await new Promise((r) => setTimeout(r, INTERVAL_MS));
    }
  }

  fs.mkdirSync(AUTH_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(AUTH_DIR, '_ready.json'),
    JSON.stringify({ ready, endpoints: ENDPOINTS, lastCodes, hadToken: !!token }, null, 2),
  );
  await info.attach('readiness', {
    body: JSON.stringify({ ready, lastCodes, hadToken: !!token }),
    contentType: 'application/json',
  });
  // NOTE: intentionally no throw — a not-ready verdict drives the scorer's --degraded
  // gate, it must not fail the project (which would SKIP dependents → vacuous green).
});
