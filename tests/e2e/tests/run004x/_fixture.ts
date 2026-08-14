import { expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * Shared fixture accessor + the precondition gate for both RUN 004-X specs.
 *
 * WHY THIS GATE EXISTS — read before "fixing" a red run by softening it.
 *
 * Both assertions need a case with vetted providers attached. When the fixture has none,
 * the natural instinct is to skip: no providers, nothing to click, not our bug. The first
 * version of these specs did exactly that, and both went green/skipped on a fixture with
 * ZERO providers while asserting nothing at all.
 *
 * That is the failure mode RUN 004-X has been stuck in since 2026-07-27. It was declared
 * "the final verification gating v0 launch", and for two weeks nobody could say whether it
 * passed — not because anyone ignored it, but because every attempt ended in a state that
 * produced no verdict. A test that silently skips forever reproduces that in CI, with the
 * added harm of looking green.
 *
 * So an empty fixture FAILS here, loudly, and names the likely cause. It is also a real
 * product defect in its own right: staged provisioning that reports `stage:
 * "shortlist_ready"` while building no shortlist is lying about the state it minted, and
 * the July notes already record this as the vendor-seeding intermittency (test-drive
 * provisioning seeds a published policy but not `company_vendor_selections`, so most
 * test-drive companies render an empty marketplace).
 */
const AUTH_DIR = path.join(__dirname, '..', '..', 'playwright', '.auth');

export interface R4xFixture {
  campaign: string;
  corridor: string;
  stage: string;
  case_id: string;
  assignment_id: string;
  session_id: string;
  shortlist_len: number | null;
  email: string;
}

export function fixture(key: 'r4x_movers' | 'r4x_decisions'): R4xFixture {
  const p = path.join(AUTH_DIR, '_run004x.json');
  if (!fs.existsSync(p)) {
    throw new Error(`${p} missing — the r4x-provision project did not run or did not complete.`);
  }
  const f = JSON.parse(fs.readFileSync(p, 'utf8'))?.fixtures?.[key];
  if (!f?.case_id) throw new Error(`no ${key} fixture in _run004x.json`);
  return f as R4xFixture;
}

export function authFile(key: string): string {
  return path.join(AUTH_DIR, `${key}.json`);
}

/**
 * Fail with a diagnosis rather than skipping. `count` is how many provider cards the page
 * actually rendered.
 */
export function assertFixtureHasProviders(f: R4xFixture, count: number, minimum: number): void {
  expect(
    count,
    `Fixture ${f.campaign} (${f.corridor} @ ${f.stage}) rendered ${count} provider cards; ` +
      `this assertion needs at least ${minimum}.\n\n` +
      'This is a FIXTURE defect, not a flaky test, and it is why RUN 004-X has never ' +
      'produced a verdict. provision-staged reported the stage was reached while building ' +
      'no shortlist — the known vendor-seeding intermittency (a published policy is seeded, ' +
      '`company_vendor_selections` is not, so the marketplace renders empty).\n\n' +
      `Case ${f.case_id}. Reproduce by opening ` +
      `/employee/case/${f.case_id}/services/recommendations as that fixture's employee.\n` +
      'Do NOT diagnose this with GET /api/cases/{id}/vendors — that endpoint returns [] even ' +
      'when the page renders ten providers, because recommendations come from ' +
      '/recommendations/batch, not the vendor directory. Measured 2026-08-10; it will send ' +
      'you down a false trail.\n\n' +
      'Do NOT resolve this by skipping. A permanent silent skip is exactly the state this ' +
      'test was written to end.',
  ).toBeGreaterThanOrEqual(minimum);
}
