import { test as setup, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * RUN 004-X fixtures — two staged test-drive sessions, minted via the API.
 *
 * WHY A SEPARATE SETUP FROM provision.setup.ts
 * --------------------------------------------
 * The Sentinel's own personas are generic HR/EMPLOYEE registrations with no corridor.
 * Both RUN 004-X assertions are corridor-specific — one needs NL_SG with a built
 * shortlist, the other FR_NO positioned *before* the shortlist so the Add flow is
 * exercised — so they need `POST /api/test-drive/provision-staged`, which mints a
 * session already advanced to a named stage.
 *
 * That endpoint is what made these checks tractable at all: walking to the same state
 * through the UI costs ~45 actions, and four consecutive manual runs died before
 * reaching the assertion.
 *
 * WHY THESE TESTS EXIST HERE AND NOT IN A CARD
 * --------------------------------------------
 * RUN 004-X was declared "the final verification gating v0 launch" on 2026-07-27. Its
 * outcome was never recorded. Three attempts to run it through a browser agent failed —
 * the most recent two by the agent erroring out before it reached step one. Two
 * assertions that matter that much should not depend on an errand being re-run by hand;
 * as Playwright specs they run on every deploy, for free, and record their own result.
 *
 * SAFETY
 * ------
 * `provision-staged` is gated three ways: the test-drive flag must be on, the campaign
 * must match `qa-*` (it refuses the live `insead-2026` cohort), and it only ever advances
 * an `is_test` company. Everything minted here is `is_test = true`, which is exactly what
 * `scripts/e2e_purge.py` reaps — with an age guard so an in-flight run is never wiped.
 */
const API = process.env.E2E_API_URL || 'https://api.relopass.com';
const APP = process.env.E2E_APP_URL || 'https://relopass.com';
const AUTH_DIR = path.join(__dirname, '..', 'playwright', '.auth');

/** Unique per run so concurrent campaigns never collide on a campaign label. */
const TAG = (process.env.RUNID || String(Date.now())).replace(/[^a-z0-9]/gi, '').toLowerCase().slice(-10);

interface Fixture {
  key: string;
  corridor: string;
  stage: string;
  /** Why this corridor/stage pair, so a future reader does not "simplify" it. */
  because: string;
}

const FIXTURES: Fixture[] = [
  {
    key: 'r4x_movers',
    corridor: 'NL_SG',
    stage: 'shortlist_ready',
    because: 'the 12-mover cap (#1699) only shows up on a corridor with >10 vetted movers',
  },
  {
    key: 'r4x_decisions',
    corridor: 'FR_NO',
    stage: 'shortlist_ready',
    // The manual card used `roadmap_ready` and clicked through category selection,
    // questions and "Get recommendations" to reach the picker. Measured 2026-08-10: at
    // roadmap_ready the recommendations page renders ZERO provider cards, so a spec that
    // navigates straight there asserts nothing. The defect under test is the 2nd+ pick
    // within a category (handleCardToggle -> logDecision), which is the same code path
    // whether the list was just generated or already built — so start from a built
    // shortlist and drop the wizard steps rather than reimplement them fragilely.
  },
];

setup('mint RUN 004-X staged fixtures', async ({ request }) => {
  setup.setTimeout(180_000);
  fs.mkdirSync(AUTH_DIR, { recursive: true });

  const minted: Record<string, Record<string, unknown>> = {};

  for (const f of FIXTURES) {
    const campaign = `qa-${f.key.replace(/_/g, '-')}-${TAG}`;

    const res = await request.post(`${API}/api/test-drive/provision-staged`, {
      data: {
        first_name: `R4x${f.key.slice(4, 8)}`,
        campaign,
        corridor_id: f.corridor,
        stage: f.stage,
      },
      // The config's 15s actionTimeout is for UI actions and is far too short here: this
      // one call drives the real case → intake → roadmap → recommendations pipeline
      // server-side. That work is the entire reason the endpoint exists (it replaces ~45
      // browser actions), so it is slow by design, not by accident.
      timeout: 120_000,
    });

    // A 404 here is a config finding, not a test failure: the test-drive flag is off, or
    // the campaign gate rejected the label. Say which, rather than failing opaquely.
    if (res.status() === 404) {
      throw new Error(
        `provision-staged returned 404 for campaign "${campaign}". Either ` +
          'RELOPASS_TEST_DRIVE_ENABLED is off in this environment, or the campaign gate ' +
          `rejected the label (it requires a qa-* prefix). Body: ${await res.text()}`,
      );
    }
    expect(res.status(), `mint ${f.key} (${f.corridor}/${f.stage}) → ${await res.text()}`).toBe(200);

    const j = await res.json();
    expect(j.stage, `${f.key}: fixture did not reach the requested stage`).toBe(f.stage);

    const employee = j.employee || {};
    expect(employee.email, `${f.key}: no employee credentials returned`).toBeTruthy();

    // Sign in via the API rather than the form: the storageState the browser projects
    // consume is just localStorage, and a UI login here would add a failure mode that
    // has nothing to do with what these tests assert.
    const login = await request.post(`${API}/api/auth/login`, {
      // The login schema takes `identifier` (email OR username), not `email`.
      data: { identifier: employee.email, password: employee.password },
      timeout: 30_000,
    });
    expect(login.status(), `${f.key}: employee login → ${await login.text()}`).toBeLessThan(300);
    const lj = await login.json();
    expect(lj.token, `${f.key}: login returned no token`).toBeTruthy();
    const user = lj.user || {};

    const state = {
      cookies: [],
      origins: [
        {
          origin: APP,
          localStorage: [
            { name: 'relopass_token', value: String(lj.token) },
            { name: 'relopass_role', value: 'EMPLOYEE' },
            { name: 'relopass_user_id', value: String(user.id || '') },
            { name: 'relopass_email', value: String(employee.email) },
            { name: 'relopass_username', value: String(user.username || employee.email) },
            { name: 'relopass_name', value: String(user.name || employee.email) },
          ],
        },
      ],
    };
    fs.writeFileSync(path.join(AUTH_DIR, `${f.key}.json`), JSON.stringify(state, null, 2));

    minted[f.key] = {
      campaign,
      corridor: f.corridor,
      stage: j.stage,
      session_id: j.session_id,
      case_id: j.case_id,
      assignment_id: j.assignment_id,
      shortlist_len: Array.isArray(j.shortlist) ? j.shortlist.length : null,
      email: employee.email,
    };
    console.log(
      `✔ ${f.key}: ${f.corridor}/${j.stage} case=${j.case_id} campaign=${campaign} ` +
        `shortlist=${minted[f.key].shortlist_len}`,
    );

    await new Promise((r) => setTimeout(r, 1500)); // gentle on the rate limiter
  }

  fs.writeFileSync(
    path.join(AUTH_DIR, '_run004x.json'),
    JSON.stringify({ tag: TAG, runid: process.env.RUNID || `local-${TAG}`, fixtures: minted }, null, 2),
  );
});
