import { test, expect } from '@playwright/test';
import { shot } from '../_helpers';
import { fixture, authFile, assertFixtureHasProviders } from './_fixture';

/**
 * RUN 004-X JOB B — adding a second pick per category must not drop the Art. 14 audit row
 * (#1696 / #1700).
 *
 * The defect: `RecommendationResults` derived accept-vs-override from rank, so every 2nd+
 * pick in a category was sent as `decision:'override'` with a null reason.
 * `POST /api/ai/decisions` correctly rejects that with 400 (override requires a reason),
 * so the audit write was silently dropped. The Alert self-dismissed after 8 seconds and
 * the selection still saved, which is why nobody noticed.
 *
 * NOTE ON WHERE THIS IS ASSERTED. It is tempting to test this against the API — it is an
 * HTTP 400, after all. That would assert the wrong thing: the API returning 400 for
 * override-without-reason is CORRECT and must keep doing so. The bug was in what the
 * frontend sends. So the only place this can be caught is a browser watching its own
 * network traffic, which is also a strictly better instrument than the manual runs had —
 * they were told to fall back to grepping the console because the agent might not have a
 * network panel at all.
 *
 * Fixture: FR_NO at `shortlist_ready`. The manual card started at `roadmap_ready` and
 * clicked through the wizard to generate recommendations; measured 2026-08-10, that page
 * renders zero provider cards at that stage, so a spec navigating straight to it asserts
 * nothing. The defect is in `handleCardToggle -> logDecision`, which runs identically
 * whether the list was just generated or already built — so start from a built shortlist.
 */
test.use({ storageState: authFile('r4x_decisions') });

interface Attempt {
  status: number;
  decision?: string;
  hasReason?: boolean;
  body?: string;
}

test('[R4X-B] adding several picks per category writes every audit row', async ({ page }, info) => {
  const f = fixture('r4x_decisions');
  const caseId = f.case_id;

  const attempts: Attempt[] = [];

  // Watch the audit endpoint directly. Record the request shape too: knowing a 400 came
  // from `override` with no reason is the difference between a diagnosis and a mystery.
  page.on('response', async (res) => {
    if (!res.url().includes('/api/ai/decisions') || res.request().method() !== 'POST') return;
    let decision: string | undefined;
    let hasReason: boolean | undefined;
    try {
      const sent = JSON.parse(res.request().postData() || '{}');
      decision = sent.decision;
      hasReason = typeof sent.reason === 'string' && sent.reason.trim().length > 0;
    } catch {
      /* body not JSON — status alone still tells us what we need */
    }
    attempts.push({
      status: res.status(),
      decision,
      hasReason,
      body: res.status() >= 400 ? (await res.text().catch(() => '')).slice(0, 300) : undefined,
    });
  });

  await page.goto(`/employee/case/${caseId}/services/recommendations`);
  await page.waitForLoadState('networkidle');

  const decline = page.getByRole('button', { name: /decline|reject|only necessary/i }).first();
  if (await decline.isVisible().catch(() => false)) await decline.click();

  const addButtons = page.getByRole('button', { name: /^Add to package$/i });
  const available = await addButtons.count();
  // The bug is specifically the SECOND pick in a category, so two is the floor. Asserted,
  // not skipped: a permanent skip is how this went unanswered for a fortnight.
  assertFixtureHasProviders(f, available, 2);

  // The bug was specifically the 2nd+ pick within a category, so add several. Re-resolve
  // the first matching button each time: adding one flips its label to "In package" and
  // re-renders the list, so a captured handle goes stale.
  const target = Math.min(available, 6);
  let added = 0;
  for (let i = 0; i < target; i++) {
    const next = page.getByRole('button', { name: /^Add to package$/i }).first();
    if (!(await next.isVisible().catch(() => false))) break;
    await next.click();
    added += 1;
    await page.waitForTimeout(600); // the audit write is fire-and-forget; let it land
  }

  await shot(page, info, 'r4x-b-after-adds');
  expect(added, 'no providers could be added — the flow did not run').toBeGreaterThan(1);

  // Give any in-flight fire-and-forget writes a moment to resolve before judging.
  await page.waitForTimeout(1500);

  const failures = attempts.filter((a) => a.status >= 400);
  const detail = failures
    .map((a) => `  ${a.status} decision=${a.decision ?? '?'} reason=${a.hasReason ? 'yes' : 'NONE'} ${a.body ?? ''}`)
    .join('\n');

  expect(
    failures,
    `${added} providers added, ${attempts.length} audit writes attempted, ${failures.length} rejected:\n${detail}\n\n` +
      'A rejected write means the Art. 14 human-oversight row was dropped. If these show ' +
      "decision=override with reason=NONE, #1691 has regressed: accept-vs-override is being " +
      'derived from rank again instead of supplied by the caller.',
  ).toEqual([]);

  // A silent zero is the other way this can lie — no requests at all would also produce
  // "no failures", while meaning the audit trail stopped being written entirely.
  expect(
    attempts.length,
    `${added} providers were added but ZERO POSTs to /api/ai/decisions were observed. ` +
      'The Art. 14 audit trail is not being written at all, which is a bigger problem than ' +
      'the 400 this test was written for.',
  ).toBeGreaterThan(0);

  test.info().annotations.push({
    type: 'note',
    description: `${added} adds → ${attempts.length} audit writes, all accepted`,
  });
});
