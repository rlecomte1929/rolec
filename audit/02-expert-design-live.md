# Expert Review — Live UI/UX (Design Reality)

**Reviewer lens:** Senior product designer reviewing the running product, page by page, against the design system's own promise.
**Method:** Source-code inspection of rendered JSX (live frontend running, but auth gates much of it; the JSX is the authoritative evidence). For full visual audit beyond layout/structure, a designer-driven session with screenshots is required — flagged as Phase 3 follow-up.

**Composite score: 5.5 / 10**

What would make it a 10:
- W1 surface (Employee Dashboard) rewritten with plain language + visual hierarchy that matches the marketing-site spec
- Zero raw `<button>` outside antigravity primitives
- Status codes (`GREEN`, `AMBER`, `fulfilled`, `invite_revoked`) never rendered as text to users
- Estimate Review has a real design (currently a list of selections + totals)
- One consistent voice across persona surfaces ("you" + sentence-case throughout)

---

## Per-surface scoring (relative to figma-spec rigor)

| Surface | Score | Top issue |
|---|---|---|
| `pages/HrCommandCenter.tsx` | **8/10** | Clean — uses antigravity Card + KPICard + RiskBadge + hrAPI wrapper. Reference implementation. Minor: `<tr onClick>` instead of accessible row pattern. |
| `pages/HrCommandCenterCaseDetail.tsx` | 6/10 | Functional but raw status codes leak (`fulfilled` etc.); icon-only buttons lack aria-label; close button `<button>✕</button>` line 399. |
| `pages/HrDashboard.tsx` | 5/10 | Helpful instructional content but still says "Field 2: Assignment ID (UUID only)" — same jargon class as W1. |
| `pages/EmployeeJourney.tsx` (legacy) | **3/10** | The W1 surface. UUID jargon (217, 243), raw "Claim state: {st}" status code (688, 733), color-only error signals. **Still rendering as of 2026-05-25.** |
| `features/platform-v2/intake/EmployeeIntakePage.tsx` (v2) | not graded | Needs separate look-at-it pass — must verify it doesn't inherit W1 issues. |
| `pages/Dashboard.tsx` (employee dashboard) | 4/10 | Empty state too bare; tab buttons lack `role="tab"`; status badges render raw `GREEN`/`AMBER`/`RED` text. |
| `pages/Auth.tsx` | 4/10 | 7 raw `<button>` elements; missing `htmlFor`/`id` label association; "Email or username" ambiguous label. |
| `pages/ServicesEstimate.tsx` (Estimate Review) | 4/10 | Bare structure — confirms W2 prior finding still live. No cap comparison, no delta callout, no policy reconciliation hierarchy. |

## Cross-cutting design-system consistency

| Pattern | Status | Evidence |
|---|---|---|
| Antigravity Button/Card/Input usage | **Inconsistent** | 37 raw `<button>`/`<input>` across Auth + admin pages; HR Command Center is consistent |
| Spacing scale (8px base per spec) | Not verifiable from source alone | Needs visual pass |
| Typographic hierarchy (h1 → h2 → h3) | **Broken** on EmployeeJourney + Dashboard (no `<h1>`) | a11y agent: "no h1 on page" |
| Status presentation | **Inconsistent** | Some surfaces use `<RiskBadge>` (good), others render raw text codes (bad) |
| Empty states | **Mostly bare** | Dashboard:64–68 "Profile is empty. Complete setup to see your relocation plan." HrCommandCenter:135 "No cases match your criteria." Both lack guidance |
| Error message tone | **Blames user** | EmployeeJourney:338 "Unable to link this assignment." doesn't say why or what to do |
| Use of color alone for state | **Yes (violation)** | Dashboard:212 missing docs in `text-[#7a2a2a]` red, EmployeeJourney:694 amber "Needs HR follow-up" — no icon, no text qualifier |

## P0 findings (design-live)

### DES-LIVE-1 — W1 surface (EmployeeJourney) still renders implementation jargon
**Files:** `pages/EmployeeJourney.tsx:217, 243, 688, 733`
**Evidence:**
- Label: "Assignment ID from HR (UUID)" (217)
- Help text: "The assignment ID is not an email address: use the UUID from HR in the right field only." (243)
- Status display: `Claim state: invite_revoked` (688, 733) — raw backend status code

**Why P0:** The employee's first-impression surface tells them about UUIDs and surfaces raw status codes. The prior April 2026 audit flagged this as P0 with a Phase-1 fix committed. As of 2026-05-25, no fix is visible.

**Recommended copy:**
- "Assignment ID from HR (UUID)" → "Case code from HR" (drop UUID; accept either email or code)
- Status code passthrough → status-to-message map: `invite_revoked` → "Invitation cancelled by HR. Contact your HR team to reissue."

### DES-LIVE-2 — Status codes leak across multiple surfaces
**Files:** `pages/HrCommandCenterCaseDetail.tsx:339-347`, `pages/Dashboard.tsx:107-109`, `pages/EmployeeJourney.tsx:688`
**Pattern:** Backend enum values rendered directly as JSX text. Examples: `GREEN`, `AMBER`, `RED`, `fulfilled`, `invite_revoked`, `pending`.
**Fix:** Single utility `statusLabel(code: string, locale?: string): string` with i18n-ready mapping. Co-located with the design system primitives so every surface gets it for free.

### DES-LIVE-3 — Estimate Review (W2) confirmed still bare
**File:** `pages/services/ServicesEstimate.tsx:48-77`
**Evidence:** Empty state with two buttons, neither visually dominant. "Next steps: 1) Select vendors 2) Request quotations 3) Receive offers 4) Decide" — generic, no cost framing, no policy comparison, no delta callout.
**Why P0:** This is the screen the strategic positioning calls out as the value-prop. The prior synthesis flagged it as the lightest surface relative to its strategic weight. Still true.
**Fix:** Implement the Side-Output A spec (color signaling per ECB FX with date stamping, per-service breakdown with multiplier transparency, exception flow integration, personal-cost callout). Estimated 3-5 weeks per prior synthesis §5.

## P1 findings (design-live)

| # | Finding | Files |
|---|---|---|
| DES-LIVE-4 | 37 raw HTML form elements bypass antigravity system | Auth.tsx (7), admin pages (~25), HR pages (5) |
| DES-LIVE-5 | Empty states are bare across surfaces | Dashboard.tsx:64-68, HrCommandCenter.tsx:135 |
| DES-LIVE-6 | Color-only signals (WCAG 1.4.1) | Dashboard.tsx:212, EmployeeJourney.tsx:694 |
| DES-LIVE-7 | Headings missing or skipped | EmployeeJourney + Dashboard have no `<h1>` |
| DES-LIVE-8 | Quote status raw codes ("fulfilled") | HrCommandCenterCaseDetail.tsx:339-347 |

## Open questions for Phase 3

1. Has the Intake Wizard v2 (`features/platform-v2/intake/EmployeeIntakePage.tsx`) inherited the W1 jargon, or is it the actual fix-in-flight?
2. Is there a `statusLabel()` utility somewhere I missed, or does each surface render codes ad-hoc?
3. Does Estimate Review have a Phase-1 design spec or AI Work Queue item with concrete UX direction?

## Reference: where the design is right

`pages/HrCommandCenter.tsx` is the canonical example: AppShell layout, antigravity Card + KPICard + RiskBadge, all data through `hrAPI` wrapper, KPI placeholders during loading, proper page subtitle. Use it as the template for refactoring the others.
