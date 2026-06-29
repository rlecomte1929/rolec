# ReloPass v2.0 — Playwright campaign (you run it, I analyze it)

Self-contained Playwright project that runs the v2.0 Testing Master Document scenarios against
**production** (https://relopass.com). You authenticate each persona **once** (storageState); the specs
reuse the saved sessions, so nothing re-logs-in per page. **Passwords never leave your shell** — the auth
step reads them from env vars you set; nothing is hardcoded.

## One-time setup

```bash
cd "ReloPass/v2-campaign"
npm install
npx playwright install chromium
```

## 1) Authenticate (the only step that touches passwords — run by you)

Set the two passwords as env vars (TestCompany accounts share one; *-demo accounts share the other),
then run the auth project. It logs each persona in once and writes `playwright/.auth/<persona>.json`.

```bash
export PW_TESTCO='Passw0rd!'     # admin@relopass.com, hr@testcompany.com, employee@testcompany.com
export PW_DEMO='Demo2026!'       # the six *-demo accounts (GlobalTech / Meridian / Nexora)
npm run auth                     # = playwright test --project=setup
```

You should see 9 sessions saved under `playwright/.auth/`. If a login selector drifted, fix it in
`tests/auth.setup.ts` (it's the only credential-touching file) and re-run.

## 2) Run the campaign (no passwords involved)

```bash
export RUNID='20260628T221441Z'   # keeps evidence under one folder; optional
npm test                          # all projects, or e.g.:
npx playwright test --project=admin
npx playwright test --project=employee
npx playwright test --project=demo
```

Evidence lands in `test-artifacts/$RUNID/`:
- `_results.json` — machine-readable results (I ingest this to score + update Notion).
- `<SCENARIO>/…png` + `_test-results/` — screenshots, traces, video on failure.
- `_html-report/` — `npm run report` to browse.

## 3) Hand back to me

Tell me when it's done (or paste `test-artifacts/$RUNID/_results.json` + point me at the screenshots).
I'll score the domains, refresh `ReloPass_Test_Report_2026-06-28.md`, and write Result + finding to the
Notion **Test Scenarios** board (32 rows).

## Notes
- **Targets prod.** Specs only create clearly-tagged throwaway data where unavoidable; I'll give you the
  cleanup list. Many scenarios are read/observe (logical-page, immigration render, vendor list).
- **Expected walls** (these are findings, not script bugs): B11 RFQ "(Soon)" (VND-05/MSG-05/DEMO RFQ);
  C2/C4/C5 missing immigration+vendors; C1 vendors mis-scoped to Munich; B10/B13/B16 UX.
- Personas + their email→env mapping: see `personas.ts`. Master-doc mapping is in that file.
