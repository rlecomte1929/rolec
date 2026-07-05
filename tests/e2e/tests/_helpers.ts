import { Page, TestInfo, APIRequestContext, expect } from '@playwright/test';

const API_BASE = process.env.E2E_API_URL || 'https://api.relopass.com';

/**
 * Liveness probe used to distinguish an app bug from a deploy-window transient.
 * Returns false on any non-200 or network error (the backend is unreachable /
 * mid rolling-restart). Kept tiny + injectable so the B13 tolerance is unit-testable.
 */
export async function probeApiHealthy(
  request: APIRequestContext,
  opts?: { api?: string; timeoutMs?: number },
): Promise<boolean> {
  const api = opts?.api || API_BASE;
  try {
    const r = await request.get(`${api}/health`, { timeout: opts?.timeoutMs ?? 5000 });
    return r.status() === 200;
  } catch {
    return false;
  }
}

/**
 * API-layer analog of the B13 tolerance: if a request came back a server error
 * (>=500) AND the backend health probe is failing, annotate the test 'environmental'
 * so the ingest reclassifies it to a non-filing ENV status. Call it right BEFORE the
 * reachability assertion. Returns true if it annotated. Assertions stay unchanged —
 * a real (backend-up) 5xx still fails and files.
 */
export async function markEnvironmentalIfDown(
  info: TestInfo,
  request: APIRequestContext,
  status: number,
): Promise<boolean> {
  if (status < 500) return false;
  const healthy = await probeApiHealthy(request);
  if (!healthy) {
    info.annotations.push({
      type: 'environmental',
      description: `API returned ${status} while backend health probe failed (deploy-window transient)`,
    });
    return true;
  }
  return false;
}

/**
 * "Logical page" assertion (master doc §1.2 / UX-LOGICAL): within ≤5s the page
 * must show meaningful content — never a permanent spinner, blank/empty-without-
 * guidance, raw error, "(Soon)"/"Coming soon" where an action is expected, or a
 * stuck widget. Returns a verdict + the signals it saw (recorded as a finding).
 */
export interface LogicalVerdict {
  ok: boolean;
  heading: string | null;
  signals: string[];
}

export interface AssertLogicalPageOpts {
  /** Injectable health probe (default: probeApiHealthy against E2E_API_URL). Used to
   *  classify a raw-error page as environmental (backend down) vs a real B13 bug. */
  probeHealthy?: (request: APIRequestContext) => Promise<boolean>;
}

export async function assertLogicalPage(
  page: Page,
  info: TestInfo,
  label: string,
  opts?: AssertLogicalPageOpts,
): Promise<LogicalVerdict> {
  const signals: string[] = [];
  // give the SPA up to 5s to render real content
  await page.waitForTimeout(500);
  let heading: string | null = null;
  try {
    const h1 = page.locator('h1').first();
    await h1.waitFor({ state: 'visible', timeout: 5000 });
    heading = (await h1.innerText()).trim();
  } catch {
    signals.push('no-h1-within-5s');
  }

  // PERMANENT spinner? Only a spinner that NEVER clears is a B10. A cold Render dyno
  // makes a slow-but-resolving load (a secondary widget, e.g. the command-center's
  // "Loading cases…" or a policy call) still spin past a few seconds — that's slow,
  // not stuck. Poll for it to clear over a generous window; flag only if it persists
  // the whole time. (History: 5s → 15s → 30s. 15s still false-flagged /hr/command-center
  // on cold-start [AIQ-1375]: its company-scoped kpis/cases query plans stay cold even
  // after the generic DB warm-up [#1170], so the first "Loading cases…" can exceed 15s.
  // 30s absorbs that; a genuinely stuck spinner never clears, so B10 stays strict.)
  const SPINNER_CLEAR_MS = 30000;
  const spinner = page.locator('[role="status"], .animate-spin, :text("Loading")');
  if (await spinner.first().isVisible().catch(() => false)) {
    const stillSpinning = await spinner
      .first()
      .waitFor({ state: 'hidden', timeout: SPINNER_CLEAR_MS })
      .then(() => false)
      .catch(() => true);
    if (stillSpinning) signals.push('permanent-spinner(B10)');
  }
  // raw error / no-retry? A raw error page is only a real B13 bug if the backend is
  // actually UP — during a Render rolling-restart (every merge to main) a data fetch
  // 5xx's and the app renders "Something went wrong" with no retry, which is an
  // environmental deploy-window transient, NOT an app defect. Probe health to tell them
  // apart: down → backend-unavailable(env) + an 'environmental' annotation the ingest
  // reclassifies to a non-filing ENV status; up → a genuine raw-error-no-retry(B13).
  const bodyText = (await page.locator('body').innerText().catch(() => '')) || '';
  if (/something went wrong|unexpected error|failed to fetch|TypeError|500|error boundary/i.test(bodyText)
      && !/try again|retry|reload/i.test(bodyText)) {
    const probe = opts?.probeHealthy ?? ((req: APIRequestContext) => probeApiHealthy(req));
    const healthy = await probe(page.request).catch(() => true); // fail-safe: unknown → treat as bug
    if (!healthy) {
      signals.push('backend-unavailable(env)');
      info.annotations.push({
        type: 'environmental',
        description: `backend health probe failed while ${label} showed an error page (deploy-window transient)`,
      });
    } else {
      signals.push('raw-error-no-retry(B13)');
    }
  }
  // "(Soon)" / Coming soon where an action is expected
  if (/\(soon\)|coming soon/i.test(bodyText)) signals.push('coming-soon-placeholder');
  // blank?
  if (!heading && bodyText.trim().length < 40) signals.push('blank-empty');

  const ok = signals.length === 0 && !!heading;
  await info.attach(`${label}-logical`, {
    body: JSON.stringify({ ok, heading, signals, url: page.url() }, null, 2),
    contentType: 'application/json',
  });
  return { ok, heading, signals };
}

/** Guidance-clarity rubric (0–4): title, labelled CTA, helper text, finishable-unaided (heuristic). */
export async function clarityScore(page: Page, info: TestInfo, label: string): Promise<number> {
  let score = 0;
  const heading = await page.locator('h1').first().innerText().catch(() => '');
  if (heading && heading.trim().length > 2) score++;                                   // (1) title
  const cta = page.getByRole('button').or(page.getByRole('link'));
  if (await cta.first().isVisible().catch(() => false)) score++;                        // (2) labelled CTA
  const helper = page.locator('p.text-sm, [class*="text-slate-500"], [class*="text-slate-400"]');
  if (await helper.first().isVisible().catch(() => false)) score++;                     // (3) helper text
  const body = (await page.locator('body').innerText().catch(() => '')) || '';
  if (heading && cta && !/\(soon\)|coming soon|no .* yet/i.test(body)) score++;         // (4) finishable
  await info.attach(`${label}-clarity`, { body: JSON.stringify({ score, heading }), contentType: 'application/json' });
  return score;
}

export async function shot(page: Page, info: TestInfo, name: string) {
  await page.screenshot({ path: testArtifact(info, `${name}.png`), fullPage: true }).catch(() => {});
}

export function testArtifact(info: TestInfo, file: string): string {
  const runid = process.env.RUNID || '20260628T221441Z';
  const scenario = (info.title.match(/\[([A-Z0-9-]+)\]/)?.[1]) || info.title.replace(/\W+/g, '_').slice(0, 40);
  return `test-artifacts/${runid}/${scenario}/${file}`;
}

/**
 * Deploy-tolerant request wrapper. Render rolling-restarts (triggered by every merge to
 * main) briefly return a gateway 502/503/504 from a restarting instance. The campaign's
 * prod-reachability preconditions (`expect(status).toBeLessThan(500)`) run with Playwright
 * `retries: 0`, so a single transient gateway error files a false-positive P0 in the Work
 * Queue (AIQ-1386, AIQ-1394 were both exactly this — a 502 in a merge-deploy window).
 *
 * Retry the request only on a gateway status (502/503/504) or a network throw
 * (ECONNRESET/timeout mid-restart), with linear backoff. A non-gateway response (a real
 * app 4xx/5xx) is returned immediately so genuine failures are still caught, and a
 * persistent gateway outage still fails after the retries — the last response is returned
 * so the caller's `< 500` assertion fails honestly. Typed on the minimal `{ status() }`
 * shape so it wraps any Playwright request (GET/PATCH/POST) and is unit-testable with a stub.
 */
const GATEWAY_STATUSES = new Set([502, 503, 504]);

export async function requestWithGatewayRetry<T extends { status(): number }>(
  send: () => Promise<T>,
  { retries = 4, backoffMs = 1200 }: { retries?: number; backoffMs?: number } = {},
): Promise<T> {
  let last: T | undefined;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      last = await send();
      if (!GATEWAY_STATUSES.has(last.status())) return last;
    } catch (err) {
      if (attempt === retries) throw err;
    }
    if (attempt < retries) {
      await new Promise((r) => setTimeout(r, backoffMs * (attempt + 1)));
    }
  }
  return last as T;
}

/** Open the persona's first case from the dashboard; returns the caseId or null. */
export async function openFirstEmployeeCase(page: Page): Promise<string | null> {
  await page.goto('/employee/dashboard');
  await page.waitForLoadState('networkidle').catch(() => {});
  // case routes look like /employee/case/<uuid>/...
  const link = page.locator('a[href*="/employee/case/"]').first();
  if (await link.isVisible().catch(() => false)) {
    const href = await link.getAttribute('href');
    const m = href?.match(/\/employee\/case\/([0-9a-f-]{8,})/i);
    if (m) return m[1];
  }
  // fall back: maybe already on a case, or a "continue" button
  const cont = page.getByRole('button', { name: /continue|open|resume|view/i }).first();
  if (await cont.isVisible().catch(() => false)) { await cont.click().catch(() => {}); }
  const m2 = page.url().match(/\/employee\/case\/([0-9a-f-]{8,})/i);
  return m2 ? m2[1] : null;
}
