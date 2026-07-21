import { test, expect } from '@playwright/test';

/**
 * AIQ-1650 (follow-up to AIQ-1641). The completion survey's two highest-value fields —
 * `testimonial_consent` (legal quote usability) and `pilot_interest` (warm-lead signal),
 * plus `referral_consent` — are CUSTOM controls: a `Consent` checkbox and tap-button
 * groups (`TapGroup`), not native radios. A prior QA run (RUN 003-C) reported them empty
 * because its programmatic clicks did not fire React's `onChange`. AIQ-1641 proved a REAL
 * click persists all three on prod.
 *
 * This guards that: tick the controls via REAL events (`.check()` / `.click()`) and assert
 * the values reach the outgoing `POST /api/test-drive/survey` request body — the exact
 * layer the false-empty happened at. Backend-free (QG-5 mocked-/api pattern): the request
 * is captured and fulfilled with a stub 200, so nothing is written to the DB and no auth
 * is needed (the survey is a public page).
 */
test.describe('test-drive survey — consent + pilot reach the payload (AIQ-1650)', () => {
  test('real clicks on the custom consent/pilot controls send the values in the survey POST', async ({
    page,
  }) => {
    // No live backend: fulfil every /api call with a stub 200 so the submit "succeeds"
    // (the page only makes POST /api/test-drive/survey; complete/notify are server-side).
    await page.route('**/api/**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, response_id: 'e2e-1650' }),
      }),
    );

    await page.goto('/test-drive/survey');

    // Required segment self-ID — a custom tap button; exact 'Yes' is the segment control
    // (the other 'Yes…' buttons are Q3 'Yes, clearly' / trust 'Yes, I think so' / pilot).
    await page.getByRole('button', { name: 'Yes', exact: true }).click();

    // Q5 — testimonial + its quote-consent checkbox (the field RUN 003-C saw empty).
    await page
      .getByRole('textbox', { name: /how would you describe ReloPass/i })
      .fill('ReloPass turns a messy relocation into one visible case.');
    await page.getByRole('checkbox', { name: /You can quote me/i }).check();

    // Q6 — pilot interest (custom tap group). 'let's talk' uniquely identifies the Yes option.
    await page.getByRole('button', { name: /let's talk/i }).click();

    // Referral consent — same custom checkbox control.
    await page.getByRole('checkbox', { name: /You can mention I referred them/i }).check();

    // Capture the outgoing request body and assert the three high-value fields carried.
    const reqPromise = page.waitForRequest('**/api/test-drive/survey');
    await page.getByRole('button', { name: /^Submit$/ }).click();
    const body = (await reqPromise).postDataJSON() as Record<string, unknown>;

    expect(body.testimonial_consent, 'testimonial_consent must reach the payload').toBe(true);
    expect(body.pilot_interest, 'pilot_interest must reach the payload').toBe('yes');
    expect(body.referral_consent, 'referral_consent must reach the payload').toBe(true);
    // Sanity: the required segment self-ID mapped 'Yes' → 'prospect'.
    expect(body.tester_segment).toBe('prospect');
  });
});
