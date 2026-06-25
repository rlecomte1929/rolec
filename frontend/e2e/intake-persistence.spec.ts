import { test, expect, Page } from '@playwright/test';
import { loginAsEmployee } from './support/auth';

/**
 * Intake persistence E2E — the literal acceptance test from the bug report:
 * fill steps 1–2 → reload → assert all fields + the current step persisted.
 *
 * Runs against a LIVE deployment (default relopass.com). It only writes the demo
 * assignment's intake DRAFT (no submit → no state transition), so it's
 * non-destructive on the pre-launch demo data. See playwright.config.ts for env
 * overrides; this suite is not CI-gated (the vitest test is the CI guard).
 */

const INTAKE_PATH = process.env.E2E_INTAKE_PATH || '/employee/intake';

/** Read an input's current value by its data-testid. */
const read = (page: Page, testId: string) => page.getByTestId(testId).inputValue();

/**
 * Pick a country in the custom CountryCombo: focus to open the dropdown, type to
 * filter, then click the matching option (the exact country name only appears in
 * the dropdown). No-op when the field is HR-locked (disabled) — it's already set.
 */
async function selectCountry(page: Page, testId: string, name: string): Promise<void> {
  const input = page.getByTestId(testId);
  if (!(await input.isEditable())) return;
  await input.click();
  await input.fill(name);
  await page.getByText(name, { exact: true }).first().click();
  await expect(input).toHaveValue(name);
}

test('intake draft + step persist across a full page reload', async ({ page }) => {
  await loginAsEmployee(page);
  // Autosave is armed only AFTER the draft-hydration GET resolves; editing before
  // that lands would not schedule a save. Gate on it to avoid that race.
  await Promise.all([
    page.waitForResponse((r) => /\/assignments\/[^/]+\/intake$/.test(r.url()) && r.ok()),
    page.goto(INTAKE_PATH),
  ]);
  await expect(page.getByTestId('intake-origin_country')).toBeVisible({ timeout: 20_000 });

  // ── Step 1 ──────────────────────────────────────────────────────────────
  await selectCountry(page, 'intake-origin_country', 'France');
  await page.getByTestId('intake-origin_city').fill('Lyon');
  await selectCountry(page, 'intake-dest_country', 'Japan');
  await page.getByTestId('intake-dest_city').fill('Tokyo');
  await page.getByTestId('intake-target_date').fill('2026-12-01');
  await page.getByTestId('intake-purpose').selectOption('Study');
  // The pets click is the last step-1 edit; assert its debounced autosave lands
  // so we know step-1 data reached the backend draft before we move on.
  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes('/intake-draft') && r.request().method() === 'PATCH' && r.ok(),
    ),
    page.getByTestId('intake-has_pets-no').click(),
  ]);

  // Capture the exact step-1 values to compare against post-reload (robust to an
  // HR-locked destination we may not have set ourselves).
  const step1 = {
    origin_country: await read(page, 'intake-origin_country'),
    origin_city: await read(page, 'intake-origin_city'),
    dest_country: await read(page, 'intake-dest_country'),
    dest_city: await read(page, 'intake-dest_city'),
    target_date: await read(page, 'intake-target_date'),
    purpose: await read(page, 'intake-purpose'),
  };

  // Advance to step 2 (goTo flushes any residual pending save first).
  await page.getByTestId('intake-continue').click();
  await expect(page.getByTestId('intake-step-indicator')).toHaveText('Step 2 / 5');

  // ── Step 2 ──────────────────────────────────────────────────────────────
  await page.getByTestId('intake-full_name').fill('Élise Moreau');
  await selectCountry(page, 'intake-nationality', 'France');
  await selectCountry(page, 'intake-passport_country', 'France');
  await page.getByTestId('intake-passport_expiry').fill('2030-05-01');
  // Blur flushes the pending debounced save immediately (the wizard's onBlur);
  // wait for that PATCH to confirm before reloading.
  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes('/intake-draft') && r.request().method() === 'PATCH' && r.ok(),
    ),
    page.getByTestId('intake-passport_expiry').blur(),
  ]);

  const step2 = {
    full_name: await read(page, 'intake-full_name'),
    nationality: await read(page, 'intake-nationality'),
    passport_country: await read(page, 'intake-passport_country'),
    passport_expiry: await read(page, 'intake-passport_expiry'),
  };

  // ── Reload — the real assertion ───────────────────────────────────────────
  await page.reload();

  // Resumes at step 2…
  await expect(page.getByTestId('intake-step-indicator')).toHaveText('Step 2 / 5', {
    timeout: 20_000,
  });
  // …with step-2 fields restored.
  await expect(page.getByTestId('intake-full_name')).toHaveValue(step2.full_name);
  await expect(page.getByTestId('intake-nationality')).toHaveValue(step2.nationality);
  await expect(page.getByTestId('intake-passport_country')).toHaveValue(step2.passport_country);
  await expect(page.getByTestId('intake-passport_expiry')).toHaveValue(step2.passport_expiry);

  // Step-1 fields restored too (navigate back).
  await page.getByTestId('intake-back').click();
  await expect(page.getByTestId('intake-step-indicator')).toHaveText('Step 1 / 5');
  await expect(page.getByTestId('intake-origin_country')).toHaveValue(step1.origin_country);
  await expect(page.getByTestId('intake-origin_city')).toHaveValue(step1.origin_city);
  await expect(page.getByTestId('intake-dest_country')).toHaveValue(step1.dest_country);
  await expect(page.getByTestId('intake-dest_city')).toHaveValue(step1.dest_city);
  await expect(page.getByTestId('intake-target_date')).toHaveValue(step1.target_date);
  await expect(page.getByTestId('intake-purpose')).toHaveValue(step1.purpose);
});
