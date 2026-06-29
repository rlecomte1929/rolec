# E2E Sentinel — automatable, self-provisioning E2E test

A repeatable end-to-end test you can launch on demand (and, in Phase 2, on every
deploy). It provisions its own throwaway test accounts, runs an API + browser
campaign against production, scores the result, and is fully purgeable.

## The 6 layers
| Layer | What | Where |
|---|---|---|
| L0 Provision | register fresh `is_test` personas (hr_a/emp_a/hr_b) via API, write sessions | `tests/provision.setup.ts` |
| L1 Preconditions | dependency-order checks + graceful empty-state | `tests/core/journey.spec.ts` |
| L2 API smoke | auth, case lifecycle, RLS, CORS, rate-limit, XSS, perf | `relopass_api_runner_patched.js` |
| L3 Browser | logical-page (no B10/B13), isolation, lifecycle, RFQ | `tests/core` + `tests/write-flow` |
| L4 Score | merge → weighted score + band + regressions | `scripts/ingest_playwright_results.py` → `scripts/campaign_scorer.py` |
| L6 Purge | delete `is_test=true` data, verify →0 | `scripts/e2e_purge.py` |

## Run it locally
```bash
# 1. one strong password for the throwaway accounts (NOT a real credential)
export RELOPASS_E2E_PASSWORD='<choose-a-strong-test-password>'
export RUNID="local-$(date +%Y%m%dT%H%M%S)"

# 2. install + run the CI layers (provision → core → write-flow)
cd tests/e2e && npm ci && npx playwright install --with-deps chromium
npx playwright test --project=provision --project=core --project=write-flow

# 3. score (from repo root)
cd ../.. 
python3 scripts/ingest_playwright_results.py --pw "tests/e2e/test-artifacts/${RUNID}/_results.json"
python3 scripts/campaign_scorer.py --no-prev
```

## Purge the test data
```bash
export DATABASE_URL='postgres://...'          # the Supabase pooler URL
python3 scripts/e2e_purge.py                  # DRY-RUN — shows what would be deleted
python3 scripts/e2e_purge.py --apply          # delete (is_test=true only) + verify →0
```
The purge is scoped strictly to `is_test = true`, which the backend sets only for
`@testco.com` / `@probe.test` accounts — it can **never** touch the `@testcompany.com`
or `@*-demo.com` demo tenants.

## Run it from GitHub Actions
Two manual workflows ship gated-OFF (no-op until you opt in):

1. **Settings → Secrets and variables → Actions**
   - Secret `RELOPASS_E2E_PASSWORD` — the throwaway-account password.
   - Secret `DATABASE_URL` — already present (used by the purge workflow).
   - Variable `E2E_CAMPAIGN_ENABLED = true` — enables the campaign workflow.
   - Variable `E2E_PURGE_ENABLED = true` — enables the purge workflow.
2. **Actions → "E2E Sentinel Campaign" → Run workflow** → provisions, runs, scores;
   the score lands in the run **Summary** and the report is uploaded as an artifact.
3. **Actions → "E2E Sentinel Purge" → Run workflow** (`apply` unchecked = dry-run).

## Phase 2 (not yet wired)
- Trigger the campaign on `push: main` with a wait-for-deploy `/health` gate.
- Slack notification (`E2E_SLACK_ENABLED` + `SLACK_WEBHOOK_URL`).
- Notion sync of `notion_candidates` via the bug-triage skill.
- Per-run auto-delete on PASS (`E2E_AUTODELETE_ENABLED`).
- Deep roadmap/vendor UX journey on a fully-provisioned case.
