# Expert Review — Accessibility (WCAG 2.1 AA)

**Reviewer lens:** Accessibility specialist. Targeting WCAG 2.1 AA conformance per typical B2B SaaS standard.
**Method:** Source-code inspection of high-traffic surfaces. Not a full automated scan (axe-core run deferred to Phase 3). Cited issues are reproducible from source.

**Composite score: 4.5 / 10**

What would make it a 10:
- Zero icon-only buttons without `aria-label`
- All form inputs paired with `<label htmlFor>` and described by error text via `aria-describedby`
- No `<div onClick>` patterns; clickable rows use proper button/`role="button"`+keyboard handlers
- Color always paired with text or icon (never color-alone)
- One `<h1>` per page, consistent heading hierarchy
- Modal dialogs trap focus and use `role="dialog"` + `aria-modal="true"`

---

## P0 findings (block users on assistive tech)

### A11Y-1 — `<input>` elements missing `htmlFor`↔`id` label association
**File:** `pages/Auth.tsx:418, 431` (login form)
**Evidence:** `<label>` elements present, but inputs lack matching `id`. Screen readers won't announce the field purpose when the user lands on it.
**Fix:** `<label htmlFor="email-or-username">…</label>` + `<input id="email-or-username" />`. Apply to all Auth form fields.
**Standard:** WCAG 1.3.1 (Info and Relationships), 4.1.2 (Name, Role, Value).

### A11Y-2 — Clickable table rows lack keyboard support
**File:** `pages/HrCommandCenter.tsx:152-171` (row → case detail)
**Evidence:** `<tr onClick>` without `tabIndex={0}`, no `onKeyDown` handler, no `role="button"`.
**Fix:** Make rows focusable with `tabIndex={0}`, add `onKeyDown` for Enter/Space, set `role="button"` (or refactor to render a wrapping `<button>` containing the row content).
**Standard:** WCAG 2.1.1 (Keyboard).

### A11Y-3 — Tab pattern not implemented with ARIA
**File:** `pages/Dashboard.tsx:167-183`
**Evidence:** Buttons styled as tabs but no `role="tablist"`/`role="tab"`/`aria-selected`/`aria-controls`. Screen readers announce them as generic buttons; the relationship to the panels they control is invisible.
**Fix:** Apply ARIA Authoring Practices Guide tab pattern (or use Radix/Headless UI Tabs if available in the design system).
**Standard:** WCAG 4.1.2, ARIA APG.

### A11Y-4 — Icon-only buttons lack `aria-label`
**Files:**
- `pages/HrAssignmentReview.tsx:667` — `<button>⋯</button>`
- `pages/HrCommandCenterCaseDetail.tsx:399` — `<button>✕</button>` close icon
- `pages/AdminLayout.tsx:56, 61, 66` — three icon-only nav buttons
- `pages/AdminOverviewPage.tsx:150` — icon-only button
- Multiple in `pages/Auth.tsx` — password toggle, etc.

**Fix:** `aria-label="Open row actions menu"`, `aria-label="Close dialog"`, etc.
**Standard:** WCAG 4.1.2 (Name, Role, Value).

## P1 findings (visible barriers)

### A11Y-5 — Color-only status signals
**Files:**
- `pages/Dashboard.tsx:212` — missing-documents list uses `text-[#7a2a2a]` red only
- `pages/EmployeeJourney.tsx:694` — "Needs HR follow-up" in `text-[#b45309]` amber only

**Why P1:** Users with color-vision deficiency, or in high-glare environments, can't distinguish state.
**Fix:** Add icon (⚠ / ⛔ / ✓) and text qualifier ("Missing: …", "Action required: …") before the colored content.
**Standard:** WCAG 1.4.1 (Use of Color).

### A11Y-6 — Missing `<h1>` on top-level pages
**Files:** `pages/EmployeeJourney.tsx`, `pages/Dashboard.tsx`
**Evidence:** `<AppShell title=…>` provides a visible title but no `<h1>` is rendered (likely `<div>` styled as a title).
**Fix:** Either render `<h1>` inside AppShell or expose `as="h1"` prop. Page titles must be semantic.
**Standard:** WCAG 1.3.1, 2.4.6 (Headings and Labels).

### A11Y-7 — Form errors not associated to fields
**Pattern across surfaces:** error messages displayed below inputs but not connected via `aria-describedby` to the input's `id`. Screen readers will skip them.
**Fix:** `<input aria-describedby="email-error" aria-invalid={hasError} />` + `<p id="email-error">…</p>`.
**Standard:** WCAG 3.3.1 (Error Identification), 3.3.3 (Error Suggestion).

### A11Y-8 — Quote/action buttons lack action context
**File:** `pages/HrCommandCenterCaseDetail.tsx:351-369`
**Evidence:** "Acknowledge" / "Mark fulfilled" buttons inline next to quotes, but each is identical text — screen-reader user hears "Acknowledge button" three times without knowing which vendor/quote.
**Fix:** `aria-label="Acknowledge quote from {vendorName} for {service}"` — composed dynamically.
**Standard:** WCAG 2.4.6, 2.4.9 (Link Purpose).

### A11Y-9 — `<div onClick>` patterns on HrDashboard rows
**File:** `pages/HrDashboard.tsx:481-550`
**Evidence:** Rows use `<div onClick>` with `role="button"` + `onKeyDown` (partially correct), but no visual focus-visible ring confirmed in grid layout.
**Fix:** Verify focus-visible ring renders correctly; consider `<button>` element with `display: block`.

## P2 findings (polish / extended scan needed)

| # | Finding | Notes |
|---|---|---|
| A11Y-10 | Color contrast on muted-gray microcopy (`text-gray-400` on white) | Likely below 4.5:1 — needs automated axe run |
| A11Y-11 | Modal dialogs across the app: do they trap focus and announce as `role="dialog"`? | Needs case-by-case audit; not enumerable from source alone |
| A11Y-12 | Skip-link missing | New users with screen readers must traverse nav on every page load |
| A11Y-13 | Live regions for status updates (case status change, error toast) | Toast/snackbar should use `role="status"` or `role="alert"` |
| A11Y-14 | Form auto-complete attributes | Login form should set `autocomplete="email"`, `autocomplete="current-password"` |

## What this pass DID NOT cover

- Full automated axe-core run (recommend in Phase 3, against the live `:3000` after a logged-in user reaches each surface)
- Mobile/touch a11y (target sizes ≥44×44 px, gesture alternatives)
- Color-contrast measurement on real rendered colors (need browser dev-tools or axe)
- Modal/dialog focus trap behavior (requires interaction)
- Real screen-reader walkthrough (VoiceOver, NVDA)

## Recommended next a11y actions

1. Add `aria-label` to every icon-only button (one batch PR, easy).
2. Fix Auth.tsx label associations (medium PR, foundational).
3. Replace `<tr onClick>` on HrCommandCenter with accessible row pattern.
4. Add ARIA tab pattern to Dashboard.tsx tabs.
5. Add `<h1>` to AppShell or top-level pages.
6. Single CI lint rule: prohibit `<div onClick>` without `role="button"` + `tabIndex` + `onKeyDown`.
7. Schedule a full axe-core scan as part of Phase 3 once a test user/session can authenticate the high-traffic surfaces.
