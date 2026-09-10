# Live authenticated-portal E2E (QG-AUTH)

A Playwright suite that signs in as **Admin, HR, and Employee** against a real
deployment (default `https://relopass.com`) and smoke-checks that each portal loads
for an authenticated user with a clean console. It complements — and never replaces —
the deterministic, backend-free preview suite that gates PRs.

## Why it exists (and what it replaced)

Audos task #132711 ("Set up Playwright end-to-end tests for the three ReloPass
authenticated portals") produced files that never reached the repo (the Audos bridge
can't run Git), and its brief would have **replaced** the CI-gating preview config with
a live, prod-targeting one — which would have broken PR gating. This is the corrected
version: the preview project is untouched; the live suite is **added beside it** and is
**opt-in**.

## The access model — "open a door, remove it"

QA agents can't type credentials into a login form safely, and we don't want a prod
auth-bypass. So the door is a **throwaway QA account + a pre-authenticated session**:

- `portals/auth.setup.ts` signs in **once per role** through the real login form and
  saves the browser session (Playwright `storageState`) to
  `frontend/playwright/.auth/<role>.json` (gitignored).
- Each `*.portal.spec.ts` reuses its role's session via the project's `storageState` —
  **no password ever appears in a spec**, and a browser agent handed the state file is
  "logged in" without seeing a secret.
- **Close the door:** sessions expire on their own; to force-close, rotate the throwaway
  account's password (or delete the CI secret / the `.auth/` files).

Accounts are the disposable throwaway users on the Notion **"QA Test Credentials"** page
(the same ones the weekly `relopass-qa-url-verify` task uses) — non-PII, against
pre-launch fake data.

## Running it

```bash
cd frontend
cp .env.test.example .env.test     # then fill from the "QA Test Credentials" Notion page
npx playwright install chromium    # first time only
npm run test:e2e:portals           # E2E_LIVE_PORTALS=1 playwright test
```

Target a different environment with `E2E_PORTAL_BASE_URL` (e.g. a preview deploy).

## Why it can't break PR CI

- PR CI runs `npx playwright test --project=chromium` (`.github/workflows/ci.yml`). The
  live projects are named `portal-setup` / `admin-portal` / `hr-portal` /
  `employee-portal`, so `--project=chromium` never selects them.
- The live projects are only added to the config when `E2E_LIVE_PORTALS=1`; CI never
  sets it.
- Portal specs are excluded by the mode-aware **top-level** `testIgnore`, so even a naked
  `playwright test` in a CI job skips them (the deterministic project stays `chromium`).

This runs automatically **nightly at 02:50 UTC** via `.github/workflows/portals-nightly.yml`
(plus `workflow_dispatch`), gated behind the repo variable `E2E_PORTALS_NIGHTLY_ENABLED`
and the six `E2E_*` credential secrets.

## Launching from Audos (Otto / QA Guru)

`audos-workspace-776786/tools/github-dispatch-portals-qa.ts` is an Audos-native trigger:
an agent (QA Guru / Otto) can launch the suite on demand instead of waiting for the nightly
cron. It calls GitHub's `workflow_dispatch` API for `portals-nightly.yml` and returns the run
URL (add `--watch` to wait for the pass/fail result).

- Requires a `GITHUB_DISPATCH_TOKEN` secret in the Audos Space (Connect Integrations): a
  fine-grained PAT scoped to the repo with **Actions: Read and write**, or a classic PAT with
  `repo` + `workflow`. Keep the scope minimal — this token can start workflows.
- QA Guru still does **not** run the test itself (it can't authenticate); it only *launches*
  the Playwright suite, which does the sign-ins. The launch stays passwordless and auditable.
- Bind the tool to the QA Guru agent in the Audos UI if you want it to appear among that
  agent's capabilities; the file is auto-discovered as a workspace tool either way.

## Scope / follow-ups

Each spec currently asserts the robust, non-brittle signals: the session held (no bounce
to sign-in), we're inside the portal, the login form is gone, the shell rendered, and the
console is clean. Deeper per-role journeys (HR opens a case, Employee views the roadmap,
Admin opens the Countries CMS) are marked `TODO(QG-AUTH follow-up)` in the specs.
