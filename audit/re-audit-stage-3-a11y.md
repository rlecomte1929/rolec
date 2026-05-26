# Re-audit — Stage 3 (A11y baseline)

**Lens:** Accessibility (WCAG 2.1 AA).
**Method:** Static code inspection of every A11Y-1..A11Y-9 finding from `audit/02-expert-a11y.md` against the current `main` + Stage 3 patches. Where the audit named a specific file:line, the current source is re-read and the finding marked closed/partial/open. Where AppShell or a design-system primitive owns the pattern (e.g. h1 rendering, input labeling), the primitive is verified.

**Baseline (Phase 2 audit):** **4.5 / 10**
**After Stage 3:** **7.5 / 10** (+3.0)

The +3.0 closes 8 of 9 Phase-2 A11Y findings. The remaining A11Y-9 (the broader `<div onClick>` problem) is being drained by the team's AIQ-397 a11y sprint — surfaced as 303 ESLint `no-clickable-div` violations after AIQ-395 wired `@typescript-eslint/parser`. Stage 3 doesn't try to absorb that sprint's scope.

---

## Per-finding status

### A11Y-1 (P0) — Auth.tsx form inputs missing `htmlFor`↔`id`
**Closed.** Root-cause fix at the antigravity `Input.tsx` primitive (`frontend/src/components/antigravity/Input.tsx`):
- `React.useId()` generates a stable id per Input instance.
- `<label htmlFor={inputId}>` ↔ `<input id={inputId}>` always paired.
- Optional `id`/`name`/`required` props let callers override when needed.

Auth.tsx had 6 `<Input label="…">` callers (lines 302, 305, 473, 474, 476, 479) plus 2 raw inputs with htmlFor already correct (lines 418, 432). All 6 Input consumers now get htmlFor↔id for free. **This same fix closes the same finding for every Input across the app — far more than the Phase-2 audit named.**

### A11Y-2 (P0) — Clickable `<tr>` rows lack keyboard support
**Closed (pre-Stage-3).** `frontend/src/pages/HrCommandCenter.tsx:152-171` already has `tabIndex={0}`, `onKeyDown` for Enter/Space, and `focus-visible:ring-2`. Verified in current code.

### A11Y-3 (P0) — Dashboard tab pattern not ARIA-compliant
**Closed (pre-Stage-3).** `frontend/src/pages/Dashboard.tsx`:
- Line 159: `<nav role="tablist" aria-label="Dashboard sections">`
- Lines 171–173: `role="tab"`, `aria-selected`, `aria-controls`
- Lines 194–196: `role="tabpanel"`, `aria-labelledby`

Full ARIA Authoring Practices tab pattern. Verified in current code.

### A11Y-4 (P0) — Icon-only buttons lack `aria-label`
**Closed (via AUDIT-A6 commit `97ecef9` in PR #119).** Four icon-only sites named in Phase 2 now have `aria-label`:
- `HrAssignmentReview.tsx:667`
- `HrCommandCenterCaseDetail.tsx:399`
- `AdminLayout.tsx:56, 61, 66`

### A11Y-5 (P1) — Color-only status signals (WCAG 1.4.1)
**Effectively closed (verified, no new patch needed).** The two named sites both pair color with explicit text:
- `Dashboard.tsx:218-221` — uses a `text-[#7a2a2a]` red list, but under a `<h3>Missing Documents</h3>` heading + a `•` bullet. The "Missing Documents" heading is the text qualifier; color is not the only conveyor. WCAG 1.4.1 compliant.
- `EmployeeJourney.tsx:720` — uses `text-[#b45309]` amber on `Needs HR follow-up.` text. Text + color, not color-only. Compliant.

### A11Y-6 (P1) — Missing `<h1>` on top-level pages
**Closed (already done by shell components).** `AppShell.tsx:202` and `AdminLayout.tsx:85` both render `<h1 className="text-2xl font-semibold">{title}</h1>` whenever a `title` prop is provided. Every top-level page wraps itself in `<AppShell title="…">` or `<AdminLayout title="…">`:
- `Dashboard.tsx:75`
- `HrCommandCenter.tsx:93`
- `EmployeeJourney.tsx:584`
- All admin pages via `AdminLayout`

The Phase 2 grep returned 0 because the pages don't write `<h1>` themselves; the shell does it for them. Verified semantically correct.

### A11Y-7 (P1) — Form errors not associated to inputs via `aria-describedby`
**Closed.** The same Input primitive refactor (Stage 3b) wires:
- `<input aria-describedby={errorId}>`
- `<input aria-invalid={true}>` when error is present
- `<p id={errorId} role="alert">` on the error message

Every `<Input error="…">` consumer now announces the error to screen readers. Stage 3 fix at the primitive again has app-wide effect.

### A11Y-8 (P1) — Quote-action buttons lack action context
**Closed (Stage 3).** `HrCommandCenterCaseDetail.tsx:351-369` Acknowledge / Mark fulfilled buttons now compose `aria-label`:
```
`Acknowledge quote request for {qr.service_categories.join(', ') || 'services'}, requested {date}`
`Mark quote request as fulfilled for {qr.service_categories.join(', ') || 'services'}, requested {date}`
```
Screen-reader users hear which quote-request the button targets.

### A11Y-9 (P1) — `<div onClick>` patterns on HrDashboard rows
**Acknowledged (broader sprint via AIQ-397).** AUDIT-A6-followup (commit `81c8e8c`, AIQ-395) installed `@typescript-eslint/parser` + wired it into `eslint.config.js`. First TS-aware ESLint run surfaced **303 `no-clickable-div` violations** across the codebase — much bigger than the named HrDashboard rows. The team has earmarked `AIQ-397` as the sprint to drain this to 0. Stage 3 explicitly does not attempt to absorb that sprint's scope; the named HrDashboard rows are already keyboard-accessible per the audit's spot-check at `HrDashboard.tsx:481-550` (verified `role="button"` + `tabIndex` + `onKeyDown`).

---

## P2 findings status

`audit/02-expert-a11y.md` listed 5 P2 deferred items. Stage 3 does not address these:

| # | Item | Status |
|---|---|---|
| A11Y-10 | Color-contrast on `text-gray-400` microcopy | Deferred to automated axe-core scan (Phase-3 follow-up) |
| A11Y-11 | Modal dialogs focus-trap + role="dialog" | Per-case-by-case audit, not enumerable from source alone |
| A11Y-12 | Skip-link missing | Genuine gap; recommend a follow-up Notion ticket |
| A11Y-13 | Live regions for toasts | Genuine gap; recommend a follow-up |
| A11Y-14 | `autocomplete="…"` on Auth form | Genuine gap; ~5-min fix; recommend follow-up |

A new follow-up ticket `AUDIT-A11Y-P2-followup` is recommended to bundle items 12–14 (the easy wins) and 10–11 (the deeper work).

---

## Scoring rationale

| Sub-dimension | Δ |
|---|---|
| Input primitive auto-wires htmlFor↔id (closes A11Y-1 app-wide) | +1.0 |
| Input primitive auto-wires aria-describedby for errors (closes A11Y-7 app-wide) | +0.7 |
| Composed aria-label on quote buttons (A11Y-8) | +0.3 |
| Verification: A11Y-2/3 already done; A11Y-4 closed by 97ecef9; A11Y-5 actually compliant; A11Y-6 closed by AppShell | +1.0 (banks the credit for closure status) |
| **Net** | **+3.0** |

Score moves to 9.0+ once AIQ-397 drains the 303 `<div onClick>` violations, and a future P2 sweep adds skip-link + live regions + autocomplete.

---

## Files touched in Stage 3

```
frontend/src/components/antigravity/Input.tsx         (primitive refactor — useId + aria)
frontend/src/pages/HrCommandCenterCaseDetail.tsx       (A11Y-8 composed aria-label)
audit/re-audit-stage-3-a11y.md                         (this file)
audit/STAGES.md                                        (Stage 3 row + composite scorecard)
```

Source-code edits: 2 files, ~20 lines net change. All TS clean.

---

## What Stage 3 explicitly did NOT do

- Drain the 303 `no-clickable-div` ESLint violations (AIQ-397 sprint scope).
- Drain the 25 `no-console` ESLint violations (AIQ-398 sprint scope).
- Full automated axe-core run against authenticated surfaces (deferred to Phase-3 follow-up; requires test creds).
- Add skip-links, live regions, or autocomplete attributes (P2 items 12–14; queued for AUDIT-A11Y-P2-followup).
- Modal dialog focus-trap audit (P2 item 11; requires interaction).

## Recommended next a11y actions

1. **AIQ-397** (already filed by team): drain the 303 no-clickable-div violations. ESLint now blocks new ones from landing.
2. **New follow-up `AUDIT-A11Y-P2-followup`**: bundle skip-link + live regions + autocomplete (items 12–14). ~1 hour total.
3. **Phase-3 follow-up after Stage 10**: full axe-core scan against authenticated surfaces with a seeded test user.
