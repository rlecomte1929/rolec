# ReloPass test-drive regression — 2026-07-17 (continuation run)

**Mode:** verify-only (no product code changed). **Prod baseline:** live frontend deploy
`fe29853b` (AIQ-1587) — one commit *ahead* of the brief's stated `c6d39304`; the A1/B/C/D/E code
paths are byte-identical between the two, so findings hold. Backend on the same line.

**Personas:** provisioned fresh under `campaign=qa-regress-0717b` via the real `/test-drive` page;
authed by minting `relopass_token` through `POST /api/auth/login` (no passwords typed into forms)
and injecting the session into the browser. All notification checks used `@probe.test` uuid
accounts (never the legacy text-id demo accounts, which cannot receive in-app notifications).

**Environment action (reverted):** every push to `main` triggers the E2E Sentinel Campaign, which
ends by running `e2e_purge.py --apply` and deletes all `@probe.test` users + their case data
mid-run (this wiped the first session). With Romain's approval, `vars.E2E_AUTODELETE_ENABLED` was
flipped `true→false` for the run and **restored to `true`** at the end.

## Scorecard

| # | Check | Verdict | Evidence |
|---|---|---|---|
| A1 | "Add your first relocation" opens the case form, not `/hr/welcome` | **FAIL** | First-time test-drive HR bounces to `/hr/welcome`; reproduced (flag unset→bounce, set→form) |
| A3 | Test-drive HR reaches case creation without the full company-profile form; corridor locked | **PASS** | `/hr/welcome` shows "Optional — the full HR setup … none needed to run the test"; New-case form has no corridor field |
| A4 | Zero Resend on a test-drive assign (#1517) | **PASS** | Assign panel: "No invite email was sent — …is a test account"; notification `email_status=null` |
| A5 | `/employee/welcome` has no "journey" (#1519) | **PASS** | Screenshot: "Your relocation starts here / roadmap / Tasks", no "journey" |
| A6 | Login social proof removed (#1519) | **PASS** | Signed-out `/auth`: no "2,882 active relocations", no "47 corridors", no "Marc B. …LIVE" ticker |
| B1 | HR creates + assigns a case via the CTA path | **PASS** | "Assignment created"; assignment `cd1e17f0` links HR→emp (uuid resolved), status `assigned` |
| B2 | HR→employee message; seniority cap | **PASS** | Message row (sender HR→recipient emp); seniority "Manager" accepted on assign |
| B3 | Employee bell: assignment + HR message; inbox thread | **PASS** | Bell "2": `ASSIGNMENT_CREATED` + `NEW_MESSAGE`; dropdown shows both |
| B4 | Employee reply → HR bell | **PASS** | HR bell `NEW_MESSAGE` ("…Oslo housing…") from the reply |
| B5 | Employee-initiated over-cap exception loop (corrected design) | **PASS (core)** | File→HR `POLICY_EXCEPTION_REQUESTED` ("25,000 NOK vs 5,000 NOK cap", no HR message); approve→emp `POLICY_EXCEPTION_DECIDED`; row in `policy_cap_requests` (not `policy_exceptions`), currency **NOK** end-to-end. CTA-show/badge/#1523-frontend-currency: **code+deploy-verified** (prop chain intact, in live bundle) — not live (needs published policy + matching-currency selection) |
| B6 | Shared plan: HR edits sync to employee | **BLOCKED** | Roadmap sync needs the intake→roadmap pipeline (not run). Ad-hoc HR task-add path 500s — see finding 2 |
| C2 | Friction event on abandonment | **PASS** | `event:friction {stage:intake, reason:confused, text:…}` written |
| C3 | Admin funnel median/drop-off reconciles with raw events | **PASS** | Overview `clicked=2/provisioned=3/completed=2` matches raw; start→hr-handoff median 28m51s, drop-off 66.7% |
| C4 | Trust/intent survey question | **PASS** | `trust_intent` field (AIQ-1559, yes/maybe/no + why), rendered in survey, aggregated in admin "Trust" scorecard |
| C5 | PostHog replay: session-linked, no recording on normal pages, masked | **PASS** | Admin per-session "Replay ↗" links; PostHog not active on a normal admin page; `disable_session_recording` default + `maskAllInputs` (code) |
| C6 | Follow-up queue + mailto + pilot-yes in-app notify (0 Resend) | **PASS** | pilot=yes lead in follow-up queue with "Email →" mailto; `TEST_DRIVE_COMPLETED` notifications `delivery_channel=in_app`, no email |
| C7 | Dashboard defaults to prospect-vs-internal split | **PASS** | "Prospect vs internal" table is a default section of the admin dashboard |
| D2 | Corridor lock + server-side coercion of a tampered corridor | **PASS** | `POST /provision corridor_id:'HACKED_XX'` → 200, coerced to `GB_US` (locked-5) |
| D3 | `/complete` sets status/completed_at + emits event; idempotent | **PASS** | `session:completed`, `event:completed` emitted **once** despite survey-complete + 2 explicit calls |
| D6 | Dashboard scoped per campaign | **PASS** | Overview `?campaign=qa-regress-0717b` returns only this campaign; insead-2026 separate & unchanged (3/16) |
| E1 | Cross-tenant IDOR blocked | **PASS** | Own case → 200; foreign-company case → **403** (exception list + case detail) |
| E2 | Malformed session id on `/complete` → 4xx not 500 | **PASS** | Malformed → **422**; valid-unknown uuid → **404 "Unknown session"** |
| E3 | Stored XSS escaped in admin testimonials | **PASS** | Payload `<img … onerror><script>` stored raw, renders as inert literal text (React auto-escape); no dialog |
| E4 | Invalid survey email validated | **PASS** | Invalid → **422** "Enter a valid email address"; valid → 200 |

**Not re-done (already verified):** A2, C1, D1, D4, D5, F3.

## Failures (filed to Notion AI Work Queue)

### 1. A1 — first-time test-drive HR bounces to `/hr/welcome` (AIQ-1568 skip defeated)
The command-center "Add your first relocation" CTA routes to `/hr/dashboard?new=1`, which is meant to
open the case form (`HrDashboard` passes `skip: wantsNewCase` to `useWelcomeRedirect`). For a
first-login HR (`relopass_welcome_seen_<id>` unset), it still redirects to `/hr/welcome`.
Deterministic repro: flag **unset** → bounce; flag **set** → form opens. Likely mechanism: the
`openNewCaseForm` effect strips `?new=1` from the URL, so on re-render `wantsNewCase` recomputes to
`false` (it reads `window.location.search`), `skip` flips `true→false`, and `useWelcomeRedirect`'s
effect re-fires. Files: `frontend/src/pages/HrDashboard.tsx:59-60,213-229`,
`frontend/src/hooks/useWelcomeRedirect.ts:25-33`.
**Severity: medium.** Mitigation: the `/hr/welcome` it lands on is the AIQ-1571 test-drive variant
with a prominent "Create your first case" CTA, so it's one extra click, not the old 3× loop.

### 2. HR add-task endpoint 500s for all task types
`POST /api/hr/cases/{case_id}/tasks` returns `500 "Failed to create task"` for every task type
(`custom`, `acknowledgment`, `document_upload`). The HR is correctly in `hr_users`
(company resolves), the case is a valid `relocation_cases` row, the `task_type` PG enum matches the
code's `VALID_TYPES` exactly, and a raw `INSERT` of the core columns
(`case_id, employee_id, org_id, task_type, title`) **succeeds** in a rolled-back probe — so the
fault is in the application path `db.create_employee_task_for_case`, not a DB constraint.
Files: `backend/main.py:6554-6600` (`create_case_task_for_hr`), `db.create_employee_task_for_case`.
**Severity: medium** (blocks HR adding ad-hoc case tasks; also blocked live B6).

## Notes (not failures)
- **B5 currency (#1523) is surface-specific and correct:** `/employee/benefits` files in the policy's
  native currency (`BenefitComparisonDashboard.tsx:343`), the estimate page files in USD
  *by design* (`PackageSummary.tsx:672`, caps USD-normalised upstream). The two surfaces dedupe on
  the same canonical category, so HR's inbox could show one benefit as two mismatched-currency asks —
  a design gap, not a regression.
- **Baseline drift:** live prod was `fe29853b` (AIQ-1587), one commit ahead of the brief's
  `c6d39304`; A/B/C/D/E code paths unchanged between them.
- **insead-2026 holds real data** (3 sessions / 16 events incl. a "romain test" pilot lead) — not
  touched; verified 3/16 before and after.

## Cleanup (proven)
- Provisioned only under `qa-regress-0717b`. Before: 3 sessions / 12 events / 2 surveys / 4 probe users.
- After purge: **0 sessions / 0 events / 0 surveys / 0 probe users / 0 companies**; case, assignment,
  messages, notifications, exception all removed.
- `insead-2026` unchanged at **3 / 16** before and after.
- `vars.E2E_AUTODELETE_ENABLED` restored to **true**.
