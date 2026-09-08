# Audos E2E Test Scenario — ReloPass Test-Drive

**Target system:** https://relopass.com/test-drive
**Executor:** Audos autonomous testing agent (black-box, browser-driven)
**Objective:** Drive the full test-drive campaign end to end across BOTH personas (HR manager + relocating employee), verify cross-persona notifications and the budget-cap enforcement, complete the run, and submit the survey — reporting PASS/FAIL with screenshot evidence at every checkpoint.

---

## 0. How to read this document (agent instructions)

- You are a machine operating a real web browser. You know nothing in advance; you discover everything from the page.
- Assertions are **UI-observable** (visible text, badges, form states, navigation). Do not assume; verify what is on screen and screenshot it.
- Each step has: **Action** (what to do), **Expected** (what should appear), **Pass** (the assertion), **On fail** (what to record).
- Use only the **synthetic test data** in §2. Never enter real personal data.
- Capture generated values into the **Variables** table (§3) as you go and reuse them.
- Take a screenshot at every **Pass** checkpoint; name it `stepNN`.
- Do not stop on a single failure — record it, then continue if the flow allows, so you produce a complete report.

---

## 1. Environment & preconditions

- **Browser:** fresh session, **logged out**, cookies cleared (use a clean/incognito context).
- **Start URL (use this EXACT url):** `https://relopass.com/test-drive?campaign=audos-e2e-01`
  - The `?campaign=audos-e2e-01` tag isolates this run from real campaign data. Do not remove it. Do not use a URL without it.
- **Viewport:** desktop, 1280×800 or larger.
- **Network:** allow the page to fully load (wait for network idle) before each assertion.

---

## 2. Synthetic test data (use these values)

| Field | Value |
|-------|-------|
| Tester first name | `Audos` |
| Tester email (optional field on landing) | `audos-e2e@probe.test` |
| Employee first name (on the HR case) | `Audos` |
| Seniority level (HR case) | `Manager` |
| Intake — passport number | `X1234567` |
| Intake — passport country | (the corridor origin country) |
| Intake — role / job title | `Software Engineer` |
| Intake — family status | `Partner + 1 child` |
| Intake — any date field | a date ~60 days in the future |
| Survey — name | `Audos Tester` |
| Survey — email | `audos-e2e@probe.test` |
| Survey — company / role | `Audos QA / Test Engineer` |
| Survey — sector | `Technology` |

For any required field not listed, enter plausible synthetic text. Never leave a required field blank.

---

## 3. Variables to capture (fill in during the run)

| Name | Where captured | Value |
|------|----------------|-------|
| `CORRIDOR` | Step 3 (e.g. "Paris → Oslo") | … |
| `HR_EMAIL` | Step 3 (HR account card) | … |
| `HR_PASSWORD` | Step 3 (HR account card) | … |
| `EMP_EMAIL` | Step 3 (Employee account card) | … |
| `EMP_PASSWORD` | Step 3 (Employee account card) | … |
| `CASE_REF` | Step 7 (case reference) | … |

---

## PHASE 1 — Landing & provisioning

### Step 1 — Load the landing page
- **Action:** Navigate to the Start URL (§1).
- **Expected:** A page titled "Test drive · ReloPass" with: a hero "Run one relocation, end to end"; a "What ReloPass is" section; a "How it works" 1–5 list; a "Before you start" section with three short clips; a "Start the test" form containing a **First name** field (required) and an **Email (optional)** field, with a **Start the test** button visible without excessive scrolling.
- **Pass:** All the above are present; the Start button is reachable without scrolling more than ~1 screen.
- **On fail:** Record which elements are missing and the scroll distance to the Start button.

### Step 2 — Provision the two accounts
- **Action:** Enter First name = `Audos`, Email = `audos-e2e@probe.test`. Click **Start the test**.
- **Expected:** The page updates in place (no full reload) to reveal a credentials block.
- **Pass:** A credentials block appears (see Step 3).
- **On fail:** Record any error/validation message and whether the button responded.

### Step 3 — Capture credentials + corridor
- **Action:** Read the revealed block.
- **Expected:** (a) a corridor line like "Your test: {CORRIDOR} — already set for you"; (b) an **HR account** card with EMAIL + PASSWORD + Copy; (c) an **Employee account** card with EMAIL + PASSWORD + Copy; (d) a **Sign in →** button; (e) an **I've completed my test** button.
- **Pass:** Capture `CORRIDOR`, `HR_EMAIL`, `HR_PASSWORD`, `EMP_EMAIL`, `EMP_PASSWORD` into §3. All five are present and non-empty. The two emails end in `@probe.test`.
- **On fail:** Record which values are missing.

---

## PHASE 2 — HR persona (create + assign the case)

### Step 4 — Enter the sign-in flow (already-logged-in guard check)
- **Action:** Click **Sign in →**.
- **Expected:** A login page (`/auth?mode=login`) with Email + Password + Sign in. *(If the browser somehow already has a session, a guard should offer to sign out — if instead you land directly in an account, record this as a FAIL of the "already-logged-in guard".)*
- **Pass:** A clean login form is shown (fresh session).
- **On fail:** Record whether you were dropped into an existing account instead of the login form.

### Step 5 — Sign in as HR
- **Action:** Enter `HR_EMAIL` / `HR_PASSWORD`. Submit.
- **Expected:** You land in the HR area (an HR welcome/onboarding page or an HR dashboard). Top-right shows the HR persona.
- **Pass:** You are authenticated as HR.
- **On fail:** Record the error; retry once.

### Step 6 — Create and assign a case
- **Action:** Find the primary action to create a relocation case. Try, in order: a "create a case / add relocation" button on the HR landing or command center; if it does not open a case form, open the **Cases** page and use **New case**. In the case form enter: Employee email = `EMP_EMAIL`; First name = `Audos`; Seniority level = `Manager`. Click **Assign**.
- **Expected:** A confirmation such as "Assignment created — an invite has been sent to {EMP_EMAIL}" and an **Open case** action.
- **Pass:** The case is created and assigned. **Also record:** did the FIRST/most-prominent create-case button open a form directly, or did it loop back to onboarding? (This is a key regression check.)
- **On fail:** Record the exact button clicked, the resulting URL, and whether it looped.

### Step 7 — Open the case (capture reference)
- **Action:** Click **Open case**.
- **Expected:** A Case Summary showing: employee `Audos`; route = `CORRIDOR`; a case **reference code**; a readiness/checkpoints section; a **shared relocation plan**; a **Policy exceptions** panel; a **Suppliers & Budget** section (EUR).
- **Pass:** Capture `CASE_REF`. All the sections above are present. Route matches `CORRIDOR`.
- **On fail:** Record missing sections or a route mismatch.

### Step 8 — HR → employee message (about the cap)
- **Action:** Open the HR **Inbox**, open the case thread, and send this message: *"Hi Audos — your relocation budget is set at the Manager tier cap. Anything above it needs my approval. Let me know if unclear."* Submit.
- **Expected:** The message appears in the thread as sent.
- **Pass:** The sent message is visible in the thread.
- **On fail:** Record whether the send control worked.

---

## PHASE 3 — Employee persona (notifications, intake, roadmap, over-cap)

### Step 9 — Switch persona to the employee
- **Action:** Sign out of HR. Navigate to `/auth?mode=login`. Sign in with `EMP_EMAIL` / `EMP_PASSWORD`.
- **Expected:** The employee area (`/employee/welcome`) with a 3-step journey (intake → roadmap → services).
- **Pass:** You are authenticated as the employee.
- **On fail:** Record the error.

### Step 10 — Assert cross-persona notifications (HR → employee)
- **Action:** Open the notification bell (top-right).
- **Expected:** An unread count ≥ 2, containing (a) a "relocation case is ready / assigned" notification and (b) a "message from your HR team" notification carrying the cap text from Step 8.
- **Pass:** BOTH notifications are present. **This proves HR→employee propagation.**
- **On fail:** Record the count and which notification is missing.

### Step 11 — Assert the shared thread on the employee side
- **Action:** Open the employee **Inbox**; open the HR thread.
- **Expected:** The thread shows the HR messages (assignment + cap message).
- **Pass:** The HR cap message is visible to the employee.
- **On fail:** Record what is missing.

### Step 12 — Complete intake
- **Action:** Open the **Intake form**. Fill every required field using §2 synthetic data (name, passport number/country, role, family status, dates, destination if asked). Submit.
- **Expected:** Intake accepts and marks the step complete; progress advances toward the roadmap.
- **Pass:** Intake submits without validation errors and the "roadmap" step unlocks.
- **On fail:** Record which field blocked submission.

### Step 13 — Reach the roadmap (the payoff)
- **Action:** Open **Roadmap**.
- **Expected:** A generated, step-by-step relocation plan with phases/tasks (immigration, admin, housing, etc.) specific to `CORRIDOR`.
- **Pass:** The roadmap renders with actual task content (not an empty or "still generating" state after a reasonable wait).
- **On fail:** Record whether it was empty, errored, or perpetually loading.

### Step 14 — Over-cap selection (automated enforcement — KEY CHECK)
- **Action:** Open **Services** (or **Benefit comparison**). Select a service/vendor whose estimated cost is clearly **ABOVE** the Manager-tier cap (choose the most expensive option available).
- **Expected:** The system recognises the selection exceeds the cap — e.g. an over-cap warning, an "exception required / needs HR approval" state, or a flagged benefit exception.
- **Pass:** An over-cap indication appears at selection time.
- **On fail:** Record that an over-cap selection was accepted silently with no warning.

---

## PHASE 4 — Reverse notification + automated exception verification

### Step 15 — Employee → HR reply (push back on the cap)
- **Action:** In the employee Inbox thread, reply: *"The Manager cap looks low for {CORRIDOR} — I'll need family housing. Can we raise it or how do I request an exception?"* Submit.
- **Expected:** The reply appears in the thread.
- **Pass:** The reply is sent and visible.
- **On fail:** Record the send behaviour.

### Step 16 — Switch back to HR and verify both signals
- **Action:** Sign out. Sign in as HR (`HR_EMAIL` / `HR_PASSWORD`). Open the notification bell, then open the case (`CASE_REF`) → **Policy exceptions** panel.
- **Expected:** (a) HR's notification bell shows the employee's reply (proves employee→HR propagation); **and** (b) the over-cap selection from Step 14 appears as a flagged **Policy Exception** on the case, with an HR notification about it — generated automatically, without anyone messaging.
- **Pass:** BOTH (a) the employee reply notification AND (b) the automated over-cap Policy Exception + HR notification are present.
- **On fail:** Record precisely which of the two is missing. *(The automated exception (b) is the highest-value assertion — flag it prominently either way.)*

---

## PHASE 5 — Completion & survey

### Step 17 — Mark the test complete
- **Action:** Return to `https://relopass.com/test-drive?campaign=audos-e2e-01` (the session should persist) and click **I've completed my test** (or the equivalent completion control shown in the flow).
- **Expected:** Navigation to the survey page (`/test-drive/survey…`).
- **Pass:** The survey page loads.
- **On fail:** Record where the click led.

### Step 18 — Complete the survey
- **Action:** Answer every question: the segment question ("Do you work in HR/mobility/relocation?" → answer **Yes**); overall experience (pick 4/5); biggest struggle (free text: "the HR create-case path"); does it solve a real problem (Yes/Somewhat); one change (free text); testimonial + tick the quote-consent box; trust/intent question if present (pick "Yes/Maybe"); pilot interest → **Yes**; referral → leave a name + contact (`Referral Person`, `referral@probe.test`). Use the §2 identity data. Submit.
- **Expected:** A thank-you confirmation state.
- **Pass:** The survey submits and a thank-you/confirmation is shown.
- **On fail:** Record which question blocked submission.

### Step 19 — Post-completion state
- **Action:** Observe the thank-you page.
- **Expected:** A confirmation message; no error.
- **Pass:** Confirmation shown.

---

## PHASE 6 — Report

Produce a structured report:

1. **Result table:** one row per Step (1–19) with PASS / FAIL / PARTIAL, the assertion outcome, and a screenshot reference.
2. **Headline assertions (call these out explicitly):**
   - Two-login sign-in worked without dropping into a wrong account (Step 4).
   - Create-case entry opened a form directly, without looping to onboarding (Step 6).
   - Cross-persona notifications fired **both** ways (Steps 10, 16a).
   - Automated over-cap → Policy Exception + HR notification fired (Steps 14, 16b).
   - Roadmap rendered with real content (Step 13).
   - Completion recorded and survey submitted (Steps 17–18).
3. **Defects:** for every FAIL/PARTIAL, describe what was observed vs expected, with the exact URL and screenshot.
4. **Overall verdict:** can a first-time user complete BOTH personas end to end unaided — yes / no — and what blocked it if no.

---

## Appendix — guardrails for the agent
- Stay entirely within `relopass.com`. Do not enter real personal data anywhere.
- The `@probe.test` accounts and the `audos-e2e-01` campaign are disposable test data by design — safe to create.
- If a step is blocked, capture the blocker and continue with the remaining independent steps so the report is complete.
- Do not attempt to fix anything — this is a read/observe test run only.
