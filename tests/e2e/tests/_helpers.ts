import { Page, TestInfo, expect } from '@playwright/test';

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

export async function assertLogicalPage(page: Page, info: TestInfo, label: string): Promise<LogicalVerdict> {
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
  // the whole time. (Was a single 5s recheck → false B10 flakes on cold-start.)
  const SPINNER_CLEAR_MS = 15000;
  const spinner = page.locator('[role="status"], .animate-spin, :text("Loading")');
  if (await spinner.first().isVisible().catch(() => false)) {
    const stillSpinning = await spinner
      .first()
      .waitFor({ state: 'hidden', timeout: SPINNER_CLEAR_MS })
      .then(() => false)
      .catch(() => true);
    if (stillSpinning) signals.push('permanent-spinner(B10)');
  }
  // raw error / no-retry?
  const bodyText = (await page.locator('body').innerText().catch(() => '')) || '';
  if (/something went wrong|unexpected error|failed to fetch|TypeError|500|error boundary/i.test(bodyText)
      && !/try again|retry|reload/i.test(bodyText)) {
    signals.push('raw-error-no-retry(B13)');
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
