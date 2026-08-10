import { test, expect } from '@playwright/test';
import path from 'path';
import { shot } from '../_helpers';
import { fixture, authFile, assertFixtureHasProviders } from './_fixture';

/**
 * RUN 004-X JOB A — every vetted mover is reachable (#1699).
 *
 * The defect: the Movers list was hard-capped at 10 with no way to see the rest, so on a
 * corridor with 12 vetted movers an employee simply never saw two of them — silently, and
 * with no error. The fix (2026-07-27) returns every vetted provider and hides the tail
 * behind a "Show N more vetted providers" control.
 *
 * The assertion is deliberately about the CONTROL and the COUNT, not about a number
 * rendered somewhere: a cap that is re-introduced would still render a tidy list of 10.
 *
 * Fixture: NL_SG at `shortlist_ready` (see run004x.setup.ts) — that corridor is used
 * precisely because it has more than 10 vetted movers, which is what makes the cap visible.
 */
test.use({ storageState: authFile('r4x_movers') });

test('[R4X-A] every vetted mover is reachable, not capped at 10', async ({ page }, info) => {
  const f = fixture('r4x_movers');
  const caseId = f.case_id;

  await page.goto(`/employee/case/${caseId}/services/recommendations`);
  await page.waitForLoadState('networkidle');

  // The analytics banner overlays the page and swallows clicks, and it comes back after
  // navigation. Dismiss it before touching anything.
  const decline = page.getByRole('button', { name: /decline|reject|only necessary/i }).first();
  if (await decline.isVisible().catch(() => false)) await decline.click();

  const movers = page.getByRole('tab', { name: /movers/i }).first();
  if (await movers.isVisible().catch(() => false)) {
    await movers.click();
    await page.waitForLoadState('networkidle');
  }

  await shot(page, info, 'r4x-a-movers-before-reveal');

  const cards = page.getByRole('button', { name: /Add to package|In package/i });
  const before = await cards.count();

  // The reveal control is the fix. Its absence with a capped list IS the regression.
  const reveal = page.getByRole('button', { name: /Show \d+ more vetted provider/i }).first();
  const hasReveal = await reveal.isVisible().catch(() => false);

  // Precondition, asserted loudly rather than skipped. Ten cards with no reveal control
  // is the #1699 cap; ZERO cards is a broken fixture. Both must be visible, not silent.
  assertFixtureHasProviders(f, before, hasReveal ? 1 : 11);

  if (!hasReveal) {
    // Reaching here means >10 cards rendered with no way to reveal more, which the
    // assertion above already treated as the cap. Belt and braces.
    throw new Error(
      `${before} movers listed and no "Show N more vetted providers" control — the #1699 ` +
        'cap is back and the tail is unreachable.',
    );
  }

  // Capture what the banner claims, then check the claim is honoured.
  const label = (await reveal.textContent())?.trim() || '';
  const promised = Number(label.match(/Show (\d+) more/)?.[1] || 0);

  await reveal.click();
  await page.waitForLoadState('networkidle');
  await shot(page, info, 'r4x-a-movers-after-reveal');

  const after = await cards.count();

  expect(
    after,
    `"${label}" was clicked but the list went from ${before} to ${after}. The control ` +
      'exists and does not actually reveal the tail, which is worse than the original ' +
      'cap — it tells the employee everything is reachable when it is not.',
  ).toBe(before + promised);

  test.info().annotations.push({
    type: 'note',
    description: `movers reachable: ${before} shown + ${promised} revealed = ${after}`,
  });
});
