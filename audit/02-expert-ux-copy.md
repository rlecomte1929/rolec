# Expert Review — UX Copy

**Reviewer lens:** Senior UX writer / content designer. The product writes for two very different personas (anxious relocating employee + accountable HR professional). Voice + clarity must serve both without code or status enums leaking through.
**Method:** Direct read of high-traffic JSX text. Brand voice doc + brand audit referenced for tone standard.

**Composite score: 4.0 / 10**

What would make it a 10:
- Zero status enums rendered as text (`invite_revoked`, `GREEN`, `AMBER`, `fulfilled`) — all mapped to plain English
- Zero "UUID"/"ID"/"Section A/B"/"Layer-2" appearing as visible copy
- Every error message tells the user what went wrong AND what to do next
- Every empty state guides to the next action, not "no data"
- Voice consistent: "you" + sentence-case + active verbs across all employee surfaces; same for HR

---

## P0 — Findings that visibly damage trust

### COPY-1 — Implementation jargon in the employee-first-impression surface
**File:** `pages/EmployeeJourney.tsx:217, 243`
**Quotes (verbatim):**
> "Assignment ID from HR (UUID)"
> "The assignment ID is not an email address: use the UUID from HR in the right field only."

**Why P0:** Employees do not know what "UUID" means. The instruction tries to compensate ("use the UUID from HR") but compounds the problem by reusing the term as if it's expected vocabulary.

**Rewrite:**
- Label: "Case code from HR"
- Help text: "Your HR team will email you a code that looks like `abc-123-…`. Paste it here. (If they sent you an email instead, paste that.)"

### COPY-2 — Raw status enums rendered as text
**Files:** `pages/EmployeeJourney.tsx:688, 733`, `pages/Dashboard.tsx:107-109`, `pages/HrCommandCenterCaseDetail.tsx:339-347`
**Quotes:** `Claim state: invite_revoked`, badge text `GREEN`/`AMBER`/`RED`, quote status `fulfilled`.

**Why P0:** Backend enum values were never meant to be user-facing. They expose database vocabulary as if it's product language.

**Rewrite (status → message map, minimum):**
| Code | User-facing |
|---|---|
| `invite_revoked` | "Invitation cancelled by HR — contact them to reissue" |
| `GREEN` | "On track" |
| `AMBER` | "Needs attention" |
| `RED` | "At risk" |
| `fulfilled` | "Quote received" |
| `pending` | "Waiting on vendor" |

Implement as a single `statusLabel(code)` utility so every surface picks it up automatically.

### COPY-3 — Error messages blame instead of guide
**File:** `pages/EmployeeJourney.tsx:338`
**Quote:** "Unable to link this assignment."
**Why P0:** The user knows it failed — they're staring at the error. They don't know **why** or **what to do**.
**Rewrite (per failure mode):**
- Email mismatch: "Your email doesn't match what HR registered. Try the email on your offer letter, or ask HR to update it."
- Code already claimed: "This case code is already claimed by another account. If that wasn't you, contact your HR team."
- Code not found: "We couldn't find that case code. Double-check the email from HR — codes look like `abc-123-…`."

---

## P1 — Quality drag

### COPY-4 — Bare empty states
**Files:**
- `pages/Dashboard.tsx:64-68` — "Profile is empty. Complete setup to see your relocation plan."
- `pages/HrCommandCenter.tsx:135` — "No cases match your criteria."

**Why P1:** Empty states are an opportunity to guide; today they describe absence.
**Rewrites:**
- Employee: "You haven't started your profile yet. Tell us your origin country, destination, and target move date — we'll build your plan from there." + primary CTA "Start your profile →".
- HR: "No cases match this filter. Try changing the risk level above, or [view all open cases]."

### COPY-5 — Vague CTAs and microcopy
**Files:** `pages/ServicesEstimate.tsx:48-77`
**Quote:** "Next steps: 1) Select vendors 2) Request quotations 3) Receive offers 4) Decide"
**Why P1:** This is a numbered list of stages, not actionable copy. The current screen is the Estimate Review (W2, P0 surface in prior synthesis); generic numbered lists undersell the value.
**Rewrite:** "Pick the vendors you want quotes from → request quotes in one click → we'll surface offers as they come in → you compare and decide."

### COPY-6 — Inconsistent terminology
**File:** `pages/HrDashboard.tsx:315-318`
**Quote (paraphrased):** "account match" vs "case attaches" vs "login matches" — used interchangeably.
**Why P1:** HR users (the buyer persona) will see this as engineer-written documentation rather than product copy.
**Rewrite:** Pick one term — "The case attaches to the employee's account when they sign in with the email or code you entered." Use it consistently.

### COPY-7 — Field labels that need context
**File:** `pages/Auth.tsx:419-426`
**Quote:** Label says "Email or username" — placeholder shows email format only.
**Why P1:** User can't tell which is expected.
**Rewrite:** Label "Email or username", helper text below: "Whatever you use to sign in. Usually the email HR has on file."

### COPY-8 — Internal vocabulary in HR-facing copy
**Files:** `pages/HrDashboard.tsx:481+`, `pages/AdminMobilityCaseInspectPage.tsx:10, 51`
**Quotes:** "Field 2: Assignment ID (UUID only)", "Enter mobility_cases.id (UUID)", "Mobility case UUID"
**Why P1:** Even though HR is more technical than employees, "UUID" + table names ("mobility_cases.id") are still developer vocabulary.
**Rewrite:** "Enter the case code (the long string of letters and numbers separated by dashes)."

---

## Cross-cutting copy patterns to fix at the system level

| Pattern | Today | Should be |
|---|---|---|
| Backend status enum → UI text | Raw codes (`GREEN`, `fulfilled`) | Single `statusLabel()` map, co-located with design system |
| ID/UUID exposure | "Assignment ID (UUID)" everywhere | "case code" / accept either email or code |
| Field-level help text | Inconsistent — sometimes placeholder, sometimes inline | One pattern: label + helper text below label, error in place |
| Action button labels | Generic ("Continue", "Submit") | Outcome-described ("Save and continue", "Send for review") |
| Empty states | "No X" only | "No X yet. Try Y → CTA" |
| Error messages | "Unable to X" | "What went wrong + how to fix it" |

## Voice consistency

Brand voice doc exists (`relopass-brand-voice` skill). Prior brand audit (2026-04-23) caught marketing-site voice issues; **the product copy has not received the same pass.** Recommend an explicit "Product copy" appendix to the brand voice doc, with the patterns above as enforceable rules.

## What this pass DID NOT cover

- Translated content (i18n is presumably not yet active; if any surface is shipped in French for the French mid-market segment, voice must be re-audited there)
- Marketing-site copy (covered by `relopass-brand-audit-2026-04-23.md`)
- Notification/email copy (HR invitation emails, status-change notifications) — not audited
- AI assistant / policy assistant copy — separate surface, may have its own voice issues

## Recommended next ux-copy actions

1. **Ship `statusLabel()` utility** + replace 10–20 status-code render sites. One-day PR.
2. **Rewrite W1 surface** (`EmployeeJourney.tsx:217, 243`) — one-day PR.
3. **Add error-message map** for the assignment-link flow — one-day PR.
4. **Empty-state pass** across the 6 highest-traffic pages — one-week effort.
5. **Add "Product copy" appendix to brand voice doc** with the cross-cutting patterns table above.
