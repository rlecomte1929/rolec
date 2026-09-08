# Audos E2E Test Scenario — ReloPass Test-Drive · RUN 002

**Target:** https://relopass.com/test-drive
**Executor:** Audos autonomous testing agent (black-box, browser-driven)
**Purpose of RUN 002:** confirm the pre-wave remediation sprint landed and that a first-time tester can now complete the **full dual-persona journey through to completion + survey** — including the previously-blocked employee payoff (a rendered roadmap in-session and a service selection). Give a **FIXED / STILL-BROKEN / PARTIAL** verdict for each RUN 001 finding this run re-checks.

> Run only after the pre-wave sprint (AIQ-1612/1613 F16/F15, 1614 F10, 1615/1616 F7/F6, 1621 F4, and fast-follow 1617/1618/1619/1620) is merged and deployed.

---

## 0. Delta from RUN 001 — what changed and what to re-verify

RUN 001 was BLOCKED at the employee back half. These fixes should now let it through:

| RUN 001 finding | RUN 002 expectation |
|-----------------|---------------------|
| F16 Services bound to a phantom empty case | Services now operates on the SAME intake case (destination inherited) |
| F15 "destination missing" dead-end after intake | No false block; the employee continues into Services |
| **F10 roadmap async (2-day SLA)** | **For test-drive, the roadmap now renders IN-SESSION right after intake — NOT a "preparing your plan / 2 working days" holding state** |
| F7 double publish → 409 stuck spinner | Single publish path with a clear success confirmation; no stuck spinner |
| F6 "Published" vs "no policy" contradiction | Policy state is consistent across views |
| F4 fresh HR has no policy | A default published policy is pre-seeded for the test-drive HR account |
| F2 silent assignment | Assigning a case shows a success confirmation + navigates to the case |
| F3 false notification badge | Bell badge count matches the notifications actually listed |
| F12 currency defaults USD on EUR corridor | Services estimate currency defaults to the destination currency (EUR) |
| F8 CSP blocks geocoding | Intake address geocoding works (no CSP violation) |

**DESCOPED for RUN 002 (do NOT attempt, do NOT fail on it):** the automated **over-cap → Policy Exception → HR notification** assertion. Root cause F14 (policy/services taxonomy mismatch) is deferred post-wave. If you happen to reach Services, a service card reading "No policy rule for this category" is EXPECTED, not a defect.

---

## 1. Environment & preconditions
- **Browser:** fresh session, **logged out**, cookies cleared (clean/incognito context).
- **Start URL (exact):** `https://relopass.com/test-drive?campaign=audos-e2e-02`
- **Viewport:** desktop, ≥1280×800.
- Wait for network idle before each assertion. Screenshot every Pass checkpoint (`stepNN`).
- Do not fix anything — observe and report only.

---

## 2. Synthetic test data

| Field | Value |
|-------|-------|
| Tester first name | `Audos2` |
| Tester email (optional landing field) | `audos-e2e2@probe.test` |
| Employee first name (HR case) | `Audos2` |
| Seniority level (HR case) | `Manager` |
| Intake — passport number | `X7654321` |
| Intake — role / job title | `Software Engineer` |
| Intake — family status | `Partner + 1 child` |
| Intake — office address (geocode step) | `Marienplatz 1, Munich` (or the destination city) |
| Intake — any date | ~60 days in the future |
| Survey — name / email | `Audos2 Tester` / `audos-e2e2@probe.test` |
| Survey — company/role / sector | `Audos QA / Test Engineer` / `Technology` |

For any required field not listed, enter plausible synthetic text; never leave a required field blank.

---

## 3. Variables to capture

| Name | Where | Value |
|------|-------|-------|
| `CORRIDOR` | Step 3 | … |
| `HR_EMAIL` / `HR_PASSWORD` | Step 3 (HR card) | … |
| `EMP_EMAIL` / `EMP_PASSWORD` | Step 3 (Employee card) | … |
| `CASE_REF` | Step 7 | … |

---

## PHASE 1 — Landing & provisioning

### Step 1 — Load the landing page
- **Action:** Navigate to the Start URL.
- **Expected:** Hero "Run one relocation, end to end", the "What ReloPass is" primer, "How it works", the videos, and a **Start the test** form (First name required, Email optional) with the Start button reachable without deep scrolling.
- **Pass:** All present; Start button within ~1 screen.

### Step 2 — Provision
- **Action:** First name `Audos2`, Email `audos-e2e2@probe.test`. Click **Start the test**.
- **Pass:** A credentials block appears in place.

### Step 3 — Capture credentials + corridor
- **Action:** Read the block.
- **Expected:** Corridor line "Your test: {CORRIDOR} — already set for you"; an **HR account** card and an **Employee account** card each with a fully-readable EMAIL + PASSWORD + Copy (F1: the email should not be truncated); a **Sign in →** button; an **I've completed my test** button.
- **Pass:** Capture all five variables. Both emails end `@probe.test`. **Record F1:** is the email fully readable now?

---

## PHASE 2 — HR persona

### Step 4 — Sign-in guard (regression, TD-BUG-2)
- **Action:** Click **Sign in →**.
- **Expected:** A clean login form (fresh session). *(If somehow already authenticated, expect a "sign out to run your test account" guard — not a silent drop into another account.)*
- **Pass:** Clean login form shown.

### Step 5 — Sign in as HR
- **Action:** Enter `HR_EMAIL` / `HR_PASSWORD`; submit.
- **Pass:** Authenticated as HR.

### Step 6 — Create and assign a case (F2 check)
- **Action:** Use the primary create-case action to open the case form. Enter Employee email `EMP_EMAIL`, first name `Audos2`, seniority `Manager`. Click **Assign**.
- **Expected (F2 FIXED):** an immediate **success confirmation** (toast) and navigation/refresh to the created case — NOT a silent greyed button with no feedback.
- **Pass:** Case assigned AND a success confirmation appeared. **Record F2 verdict.**

### Step 7 — Open the case
- **Action:** Open the case.
- **Expected:** Case Summary: employee `Audos2`; route = `CORRIDOR`; a reference code; shared plan; Policy exceptions panel; Suppliers & Budget (EUR).
- **Pass:** Capture `CASE_REF`. Route matches `CORRIDOR`.

### Step 8 — Policy state consistency (F4, F6, F7 checks)
- **Action:** Open the **Policy** area (Policy Builder + Published-policy tab).
- **Expected (F4 FIXED):** a default published policy already exists for this test-drive HR account (no "employees can't compare against policy" blocker). **(F6 FIXED):** the "Published" badge and the Published-policy tab AGREE — no contradiction. **(F7 — only if you choose to publish):** publishing uses ONE clear path with a success confirmation; no stuck "Publishing…" spinner; no two competing publish buttons racing to a 409.
- **Pass:** Policy state is consistent (F6); a default policy is present (F4); if you publish, it confirms cleanly (F7). **Record each verdict.**

### Step 9 — HR → employee message (send the CAP message)
- **Action:** Open the HR **Inbox** → the case thread → send: *"Hi Audos2 — your budget is set at the Manager tier cap. Anything above it needs my approval."* Submit.
- **Expected:** The message shows as sent. *(This is deliberate: RUN 001 only produced 1 employee notification because this message was never sent. Sending it means Step 12 should show TWO.)*
- **Pass:** Message sent and visible.

---

## PHASE 3 — Employee persona (notifications, intake, ROADMAP, Services)

### Step 10 — Switch to the employee
- **Action:** Sign out of HR. Go to `/auth?mode=login`. Sign in with `EMP_EMAIL` / `EMP_PASSWORD`.
- **Pass:** Authenticated as the employee (`/employee/welcome`).

### Step 11 — Cross-persona notifications (F3 + HR→employee)
- **Action:** Open the notification bell.
- **Expected:** An unread count that MATCHES the list (F3 FIXED — no false badge). The list contains BOTH (a) the case-assigned notification and (b) the HR cap message from Step 9.
- **Pass:** Badge count == number of listed notifications; BOTH notifications present. **Record F3 verdict + "HR→employee = 2 notifications".**

### Step 12 — Shared thread
- **Action:** Open the employee **Inbox** → the HR thread.
- **Pass:** The HR messages (assignment + cap) are visible to the employee.

### Step 13 — Complete intake (F8 geocoding + auto-save regression)
- **Action:** Open the **Intake form**. Fill all required fields (use §2). On the office-address step, enter the address and trigger geocoding.
- **Expected (F8 FIXED):** address geocoding resolves with no CSP violation in the console. Intake submits and marks complete. *(Optional auto-save regression: if the session drops, intake should resume with fields intact.)*
- **Pass:** Intake submits; geocoding worked. **Record F8 verdict.**

### Step 14 — ROADMAP renders IN-SESSION (F10 — THE headline check)
- **Action:** Open **Roadmap** immediately after intake.
- **Expected (F10 FIXED):** a **fully-rendered, step-by-step roadmap appears in-session** (immigration/admin/housing tasks for `CORRIDOR`). It must NOT show "We're building your roadmap… within 2 working days" / "Preparing your plan". *(On a Tier-A corridor — Paris→Oslo or India→Munich — expect substantive content. On a Tier-B corridor, a thin/early-coverage roadmap is acceptable — do not fail on sparseness.)*
- **Pass:** A rendered roadmap with real task content is shown in-session, no 2-day holding state. **Record F10 verdict — this is the most important assertion of RUN 002.**
- **On fail:** Record whether it showed the holding state, was empty, or errored.

### Step 15 — Services on the SAME case (F15/F16 + F12)
- **Action:** Open **Services** / **Benefit comparison**. Proceed through preferences and select a service/vendor.
- **Expected (F16/F15 FIXED):** Services operates on the SAME intake case — the destination is inherited; NO "destination missing" block; NO phantom second case. **(F12 FIXED):** the estimate currency defaults to the destination currency (EUR for a Munich corridor), not USD. You can select a vendor and see an **estimated cost**. *(F14 DESCOPED: "No policy rule for this category" cards are EXPECTED — do not treat as a defect and do not attempt the over-cap flow.)*
- **Pass:** Services continues on the intake case with the destination present; currency is correct; a vendor with an estimated cost can be selected. **Record F15/F16 + F12 verdicts.**

---

## PHASE 4 — Reverse notification (employee → HR)

### Step 16 — Employee replies; verify HR is notified
- **Action:** In the employee Inbox thread, reply: *"The Manager cap looks low for {CORRIDOR} — I'll need family housing. Can we discuss?"* Submit. Then sign out, sign in as HR, open the notification bell.
- **Expected:** HR's bell shows the employee reply (proves employee→HR propagation).
- **Pass:** HR received the employee-reply notification. **Record "employee→HR notification = PASS".**
- **Note:** Do NOT assert an automated Policy Exception here — that path (F14) is descoped for RUN 002.

---

## PHASE 5 — Completion & survey (now with a real payoff behind it)

### Step 17 — Mark complete
- **Action:** Return to `https://relopass.com/test-drive?campaign=audos-e2e-02`; click **I've completed my test**.
- **Expected:** Navigation to the survey.
- **Pass:** Survey page loads.

### Step 18 — Complete the survey
- **Action:** Answer every question: segment ("Do you work in HR/mobility/relocation?" → **Yes**); overall (4/5); biggest struggle (free text); problem-fit (Yes/Somewhat); one change (free text); testimonial + tick quote-consent; trust/intent → **Yes/Maybe**; pilot interest → **Yes**; referral (name + `referral@probe.test`). Submit.
- **Expected:** A thank-you confirmation.
- **Pass:** Survey submits; confirmation shown.

---

## PHASE 6 — Report

1. **FIXED / STILL-BROKEN / PARTIAL table** for each re-checked RUN 001 finding: F16, F15, **F10**, F7, F6, F4, F2, F3, F12, F8, plus F1 (email truncation) and TD-BUG-2 (sign-in guard).
2. **PASS/FAIL table** for every Step 1–18 with evidence (screenshot / observed text).
3. **Headline verdict — call out explicitly:**
   - Employee reached a **rendered roadmap in-session** (F10) — the payoff.
   - Employee completed **intake → roadmap → Services (same case) → vendor with cost** with no dead-end (F15/F16).
   - Cross-persona notifications fired **both** ways, and the employee saw **2** notifications (Steps 11, 16).
   - Policy publish + state were clean (F4/F6/F7); assignment confirmed (F2).
   - Completion recorded and survey submitted (Steps 17–18).
4. **Overall verdict:** can a first-time user now complete BOTH personas end to end unaided — yes / no — and what (if anything) still blocks it.
5. **New/regressed issues:** file each as a Notion AI Work Queue task (do not fix in this run).

---

## Appendix — guardrails
- Stay within `relopass.com`; enter only synthetic data. The `@probe.test` accounts and `audos-e2e-02` campaign are disposable by design.
- If a step blocks, record it and continue the remaining independent steps so the report is complete.
- Over-cap / Policy Exception is intentionally out of scope for RUN 002 — do not attempt it and do not fail the run on its absence.
