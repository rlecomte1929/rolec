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
 * ── WHY THE WAITING CHANGED (rewritten 2026-08-11) ──────────────────────────────────────
 *
 * The first version counted POSTs with a passive `page.on('response')` listener and slept
 * fixed intervals — 600 ms after each click, 1500 ms at the end. It failed **5 of 12**
 * consecutive campaign runs (42%), always on "ZERO POSTs were observed", and was baselined
 * as an intermittent product bug: "the write races".
 *
 * It was not a product bug, and nothing raced. Measured against production:
 *
 *   - the POST fires, returns **201**, and the row lands — `ai_decisions` was taking
 *     ~134 rows in six hours throughout, and the picks visibly committed every time;
 *   - the request takes **~2250 ms** (`create_ai_decision` does two extra DB round-trips
 *     for company resolution, then the insert, then an audit_log insert);
 *   - the old test's budget for the LAST click was `600 + 1500 = 2100 ms`.
 *
 * So the response arrived after the listener stopped caring. A ±10% swing in API latency
 * decided the verdict — a coin flip, which is what 42% is. Proof it was the instrument and
 * not the app: with a `waitForResponse` registered before the click, the same code on the
 * same page returned `GOT 201` and both responses appeared; without it, zero, while the
 * requests were provably fired and the rows provably written.
 *
 * The fix is to WAIT FOR the response rather than sleep and hope. Every click now registers
 * its waiter before clicking, so latency can vary freely without changing the verdict.
 *
 * Asserting the row through `GET /api/ai/decisions` would be better still — the row is the
 * compliance property, the request is only a proxy for it — but that endpoint is
 * `require_admin_or_hr` and this fixture is an employee. An employee may write an audit
 * decision and may not read one. Worth revisiting if a case-scoped read ever exists.
 *
 * Fixture: FR_NO at `shortlist_ready`, which pre-shortlists the top 3 per category, so
 * every click here is a rank>0 comparison pick with the top match already in the package —
 * i.e. an `accept`, which is precisely the case that used to be mis-sent as `override`.
 */
test.use({ storageState: authFile('r4x_decisions') });

interface Attempt {
  status: number;
  decision?: string;
  hasReason?: boolean;
  body?: string;
  ms: number;
}

const isAuditPost = (url: string, method: string) =>
  url.includes('/api/ai/decisions') && method === 'POST';

test('[R4X-B] adding several picks per category writes every audit row', async ({ page }, info) => {
  const f = fixture('r4x_decisions');

  await page.goto(`/employee/case/${f.case_id}/services/recommendations`);
  const decline = page.getByRole('button', { name: /decline|reject|only necessary/i }).first();
  if (await decline.isVisible().catch(() => false)) await decline.click();

  // Retrying, not a one-shot count. The page hydrates in two dependent async steps
  // (assignments overview -> services state), so a lull between them satisfies
  // `networkidle` while the empty state is still rendered. The previous one-shot
  // `addButtons.count()` read that as a fixture with no providers and blamed provisioning.
  const addButtons = page.getByRole('button', { name: /^Add to package$/i });
  await expect
    .poll(() => addButtons.count(), {
      timeout: 30_000,
      message:
        'no "Add to package" button appeared within 30s. The page hydrates in two ' +
        'dependent fetches; if this times out the shortlist genuinely never arrived.',
    })
    .toBeGreaterThan(0);

  const available = await addButtons.count();
  // The bug is specifically the SECOND pick in a category, so two is the floor. Asserted,
  // not skipped: a permanent skip is how this went unanswered for a fortnight.
  assertFixtureHasProviders(f, available, 2);

  const attempts: Attempt[] = [];
  const target = Math.min(available, 6);
  let added = 0;

  for (let i = 0; i < target; i++) {
    // Re-resolve each time: adding one flips its label to "In package" and re-renders,
    // so a captured handle goes stale.
    const next = page.getByRole('button', { name: /^Add to package$/i }).first();
    if (!(await next.isVisible().catch(() => false))) break;

    const inPackageBefore = await page.getByRole('button', { name: /In package/i }).count();

    // Register the waiter BEFORE the click. This is the whole fix: the audit write is
    // fire-and-forget from the browser and slower than any fixed sleep this test can
    // justify, so we wait for it explicitly instead of racing it.
    const started = Date.now();
    const waiter = page
      .waitForResponse((r) => isAuditPost(r.url(), r.request().method()), { timeout: 30_000 })
      .then(async (r) => {
        let decision: string | undefined;
        let hasReason: boolean | undefined;
        try {
          const sent = JSON.parse(r.request().postData() || '{}');
          decision = sent.decision;
          hasReason = typeof sent.reason === 'string' && sent.reason.trim().length > 0;
        } catch {
          /* body not JSON — status alone still tells us what we need */
        }
        attempts.push({
          status: r.status(),
          decision,
          hasReason,
          body: r.status() >= 400 ? (await r.text().catch(() => '')).slice(0, 300) : undefined,
          ms: Date.now() - started,
        });
      });

    await next.click();
    added += 1;

    // The pick itself is local state and commits fast; assert it rather than sleeping.
    await expect(page.getByRole('button', { name: /In package/i })).toHaveCount(
      inPackageBefore + 1,
      { timeout: 15_000 },
    );

    await waiter;
  }

  await shot(page, info, 'r4x-b-after-adds');
  await info.attach('audit-writes', {
    body: JSON.stringify({ available, added, attempts }, null, 2),
    contentType: 'application/json',
  });

  expect(added, 'no providers could be added — the flow did not run').toBeGreaterThan(1);

  // One audit write per pick. `waitForResponse` already proved each one arrived, so this
  // can no longer fail because a response was slow — only because one was never sent.
  expect(
    attempts.length,
    `${added} providers were added but only ${attempts.length} audit writes were sent. ` +
      'Each click registers its waiter before clicking with a 30s budget, so this is not a ' +
      'timing artefact: a pick committed without attempting its Art. 14 row.',
  ).toBe(added);

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

  const slowest = Math.max(...attempts.map((a) => a.ms));
  test.info().annotations.push({
    type: 'note',
    description: `${added} adds → ${attempts.length} audit writes, all accepted (slowest ${slowest}ms)`,
  });
});
