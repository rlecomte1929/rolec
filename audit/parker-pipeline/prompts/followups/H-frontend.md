# FOLLOW-UP PROMPT — H-frontend: Conjoint employee flow + HR results page

_This is a deferred follow-up to step H. Run it manually when you're ready to
ship the conjoint UI. It is **not** part of the auto-chain. Paste this whole
file into Claude Code yourself._

## Pre-flight checklist (you, Romain, do this before pasting)

- [ ] Step H's PR is merged. `conjoint_studies`, `conjoint_responses`,
      `conjoint_results` tables exist.
- [ ] Endpoints `POST /api/hr/{company_id}/conjoint/studies`,
      `GET .../next-choice-set`, `POST .../responses`, `POST .../fit`,
      `GET .../results` are all live.
- [ ] You have at least one fixture study seeded for end-to-end testing.

## Task body

**UI impact: SIGNIFICANT.** Two new pages:

1. **Employee-facing choice flow** — `/journey/conjoint/{studyId}`, presents
   8–12 forced-choice questions. This is an employee-touched flow, so design
   discipline matters.
2. **HR-facing results page** — `/hr/conjoint`, shows part-worth chart, bundle
   simulator, optional push-to-priors button.

Per Romain's UI-reuse mandate, write **two** UI-PROPOSAL files (one per page)
and STOP for approval before any frontend code.

### Stage 1 — Two UI-PROPOSAL files (write these first, then STOP)

#### File 1: `audit/parker-pipeline/runs/<RUN_ID>/H-frontend/UI-PROPOSAL-employee.md`

- **Purpose**: "Capture 8–12 forced-choice preference responses from employees
  so HR can quantify benefit value."
- **Info architecture**: lazy-loaded under `/journey`. Existing pattern: read
  the closest existing journey step component and cite it as the model.
- **Reused components**: list specific antigravity primitives (Card, Button,
  RadioGroup or equivalent) + the journey shell.
- **New components**: only what cannot be done with existing primitives.
- **Closest existing analogue**: find the closest `/journey/*` step that has
  similar mechanics (choose between options + persist + advance). Cite path.
- **Visual mock**: ASCII sketch — header, "Question N of M", two bundle cards
  side by side with attribute rows, "Choose A / Choose B" buttons, progress
  bar.
- **Open questions**: should we let the employee go back? Mobile breakpoint?
  How do we show attribute icons? Do we randomise card order per question?

#### File 2: `audit/parker-pipeline/runs/<RUN_ID>/H-frontend/UI-PROPOSAL-hr.md`

- **Purpose**: "Show HR admins which benefits employees value most and let them
  simulate proposed bundles."
- **Info architecture**: `/hr/conjoint`, HR-admin only.
- **Reused components**: Card, Table, Recharts BarChart (already in stack), the
  existing HR command center layout shell.
- **New components**: bundle-builder might need a simple Form-like primitive —
  reuse antigravity if possible.
- **Closest existing analogue**: the closest HR command center analytics page.
  Cite path.
- **Visual mock**: ASCII sketch — header, part-worths bar chart per attribute,
  bundle simulator with attribute selectors and a "Predicted share: X%" output,
  "Push to benefit priors" button (only enabled if step B shipped).
- **Open questions**: how to display CIs on part-worths, default ordering of
  attributes (by importance? alphabetical?), whether to expose multinomial logit
  fit diagnostics.

Then write `BLOCKED.md` with "Waiting on UI-PROPOSAL approvals (2 files)" and
STOP.

### Stage 2 — After approval, build it

Once Romain greenlights both proposals:

1. **Employee flow:**
   `frontend/src/features/conjoint/EmployeeChoiceFlow.tsx`.
   Wire to `GET .../next-choice-set` and `POST .../responses`.
   Lazy-load in App.tsx under `/journey`. Use the journey shell for header/nav.
2. **HR results page:**
   `frontend/src/features/hr/conjoint/ConjointResultsPage.tsx`.
   Wire to `GET .../results` and the fit endpoint.
   Lazy-load under `/hr` with HR-admin guard.
   Bundle simulator: local React state, calls `simulate_market_share` via a
   dedicated POST `.../simulate` endpoint (add it if absent in H's backend).
   "Push to benefit priors" button only shown if a feature flag detects step B
   shipped (probe a static endpoint OR a build-time env var).
3. **Tests:**
   - `EmployeeChoiceFlow.test.tsx`: navigates 8 questions, submits, shows
     completion state.
   - `ConjointResultsPage.test.tsx`: renders part-worth chart, bundle simulator
     updates predicted share when attribute changes.

### Closeout

Same as the standard pipeline closeout. Branch:
`audit/parker-step-H-frontend`. PR: `audit(parker-H-frontend): conjoint UI`.

Write RESULT.md with screenshots (or screenshot-equivalents — Playwright HTML
snapshots are fine).
