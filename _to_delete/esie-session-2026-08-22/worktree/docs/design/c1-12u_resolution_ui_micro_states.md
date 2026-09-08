# C1-12U · Resolution UI — Micro-States Handoff Spec

**Task**: AIQ-502 · C1-12U
**Author**: Claude Cowork via notion-task-executor + design:design-handoff
**Date**: 2026-06-03
**Owner**: Romain (review) · C1-12 frontend engineer (implementation)
**Depends on**: C1-11D tokens (shipped) · C1-11A backend resolve/escalate endpoints (PR #242 / AIQ-570 in Validation)
**Unblocks**: C1-12 implementation

---

## 1. Purpose

The Resolution UI is the surface where HR resolves cross-document contradictions surfaced by C1-09 (e.g. passport DOB ≠ contract DOB, marriage cert spouse name ≠ employee declared spouse). This spec defines every state the engineer must build so that interaction nuance is decided here, not at 5 p.m. on Friday.

Six required states + two optional sub-states are documented below. Token references map to `design/system/tokens.css` (C1-11D).

---

## 2. Component anatomy

The Resolution UI is a single composite component, `<ContradictionResolverCard />`, rendered inside the HR Dashboard Case Detail page (route `/hr/cases/:caseId/contradictions/:contradictionId`).

```
┌──────────────────────────────────────────────────────────────┐
│  Header  · type · severity badge · case ref                   │  ← row 1, 48px
├──────────────────────────────────────────────────────────────┤
│  Side-by-side evidence panes                                  │  ← row 2, fluid
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │ Doc A excerpt    │  │ Doc B excerpt    │                   │
│  │ bbox citation 🔗 │  │ bbox citation 🔗 │                   │
│  └──────────────────┘  └──────────────────┘                   │
├──────────────────────────────────────────────────────────────┤
│  Action bar  · primary · secondary · tertiary                 │  ← row 3, 64px
└──────────────────────────────────────────────────────────────┘
```

| Region | Width | Height | Tokens |
|---|---|---|---|
| Card outer | `max-w-[840px]` desktop · 100% mobile | auto | `--surface-elevated`, `--radius-lg`, `--shadow-md` |
| Header row | 100% | 48 px fixed | `--font-heading-sm`, padding-x `--space-4`, gap `--space-2` |
| Evidence pane (×2) | 50% on ≥768 px · 100% stacked below | min 160 px, max 320 px | `--surface-recessed`, `--radius-md`, padding `--space-3` |
| Action bar | 100% | 64 px fixed | gap `--space-2`, padding-x `--space-4`, top border `--border-subtle` |
| Severity badge | auto | 22 px | `--badge-high-bg` / `--badge-mid-bg` / `--badge-low-bg` |

---

## 3. State machine

```
        ┌──────────┐
        │   IDLE   │  ← initial render, evidence visible, action bar enabled
        └─────┬────┘
              │  user clicks primary action ("Keep this version")
              ▼
        ┌──────────┐
        │ LOADING  │  ← optimistic UI, server-resolving, ≤2 s budget
        └─┬──┬──┬──┘
          │  │  │
          │  │  └────────────────► ERROR  (network / 5xx / 409)
          │  └───────────────────► ESCALATED  (HR clicked "Escalate")
          ▼
        ┌──────────┐
        │ SUCCESS  │  ← winner confirmed, contradiction collapses
        └──────────┘

Disjoint state:
        ┌──────────┐
        │  FROZEN  │  ← Pathway B2C entered, HR must act before employee can continue
        └──────────┘

FROZEN can co-exist with any other state via overlay (see §3.6).
```

Total states documented: **6 primary + 2 conditional sub-states = 8**.

---

## 3.1 IDLE — initial render

**Purpose**: Default state. HR sees both evidence panes side-by-side, can interact with citations, and choose an action.

**Visual**:
- Both evidence panes fully visible at full opacity.
- Action bar shows three buttons: `Keep Doc A`, `Keep Doc B`, `Escalate to HR Director`.
- A subtle pulse animation (1× on mount, 200 ms) draws attention to the severity badge for HIGH-severity contradictions only — disabled at `prefers-reduced-motion: reduce`.

**Dimensions** (desktop ≥1024 px):
- Card: 840 × auto, centered with 24 px page padding.
- Evidence panes: 408 × 240 px (≈ phi ratio at the doc-clip aspect of typical OCR snippets).
- Buttons: 44 px height (`--touch-target-min`), padding-x `--space-4`.

**Tokens** (C1-11D):
- Card surface: `--surface-elevated` (#FFFFFF light · #1A1F2E dark)
- Card border: `--border-subtle` (1 px)
- Primary button: `--button-primary-bg` (#0A56FF) → text `#FFFFFF`
- Secondary button: `--button-secondary-bg` (transparent) + 1 px `--border-default`
- Tertiary "Escalate" button: text `--text-warning` (#A85C00), no fill
- Severity HIGH badge: `--badge-high-bg` (#FCE5E5) text `--badge-high-text` (#7A0000)

**ARIA**:
```html
<section
  role="region"
  aria-labelledby="contradiction-{id}-title"
  aria-describedby="contradiction-{id}-desc"
>
  <h2 id="contradiction-{id}-title">Date of birth disagrees · Passport vs Employment contract</h2>
  <p id="contradiction-{id}-desc" class="sr-only">
    Passport reads 12 April 1989. Contract reads 12 April 1990.
    Choose which value to keep, or escalate to a director.
  </p>
  <div role="group" aria-label="Evidence" class="evidence-grid">…</div>
  <div role="group" aria-label="Resolution actions" class="action-bar">…</div>
</section>
```

**Animation**:
- Mount: card fade-in `opacity 0 → 1` over **200 ms**, ease-out (`--motion-emphasis`).
- HIGH-severity badge pulse: scale 1 → 1.05 → 1 over **400 ms**, twice on mount, then stop.

---

## 3.2 LOADING — server resolving

**Purpose**: HR has clicked "Keep Doc A" or "Keep Doc B". UI commits optimistically; server confirms in ≤2 s. If the server replies later than that, see §3.6 latency-fallback.

**Visual changes from IDLE**:
- Chosen pane gets a 2 px `--border-success` ring (`#1F7A3D`) + a 16 px checkmark icon in its top-right corner, animated in.
- Other pane reduces to `opacity-50` and `filter: grayscale(0.4)`.
- Action bar buttons disable (`disabled`, `aria-busy="true"`); primary button label switches to `"Saving…"` and shows a 16 px spinner (left of label).

**Dimensions**: identical to IDLE — no layout shift.

**Tokens**:
- Winning pane ring: `--border-success` (#1F7A3D), 2 px.
- Losing pane: `opacity-50` + `grayscale-40`.
- Spinner: 16 px, color `--text-on-primary`.

**ARIA**:
- `aria-busy="true"` on the action-bar group.
- Live region announcement: `<div role="status" aria-live="polite">Saving your choice…</div>`
- `aria-disabled="true"` on all three buttons (use this rather than `disabled` to keep focus, so screen readers can still announce them).

**Animation**:
- Checkmark scale-in: 0 → 1 over **100 ms**, ease-out.
- Losing pane fade-to-grayscale: **200 ms**, ease-in-out.
- Spinner: 360° rotation continuous, **800 ms** per cycle, linear.

**Timing budget**:
- Optimistic transition fires immediately on click.
- If server hasn't replied at **1500 ms**, the live region updates to "Still saving…" once.
- At **3000 ms** without reply, transition to ERROR (timeout) — see §3.7.

---

## 3.3 SUCCESS — winner confirmed, contradiction collapses

**Purpose**: Server confirmed. The contradiction is resolved. Card shrinks to a single-line confirmation that animates out of the list.

**Visual**:
- Both evidence panes collapse into a 1-line summary: "✅ Resolved · kept passport value 12 April 1989 · {timestamp} · by {HR user}".
- Severity badge swaps to a neutral "Resolved" pill (`--badge-success-bg`).
- Action bar replaced by single tertiary link `Undo (5 s)` that fires a CSS countdown.
- Card height animates from auto → 48 px → 0 (with `aria-hidden="true"` at final frame).
- After 5 s and no Undo click, the parent list re-flows.

**Dimensions**:
- Collapsed card: 100% width × 48 px during the 5-s undo window, then animates to 0.

**Tokens**:
- Resolved pill: `--badge-success-bg` (#E5F5EB) text `--badge-success-text` (#0F3E1F)
- Undo link: `--text-link` color
- Countdown bar: `--surface-recessed` underline, 2 px high, animates left→right 0 → 100% over 5 s

**ARIA**:
- `<div role="status" aria-live="polite">Contradiction resolved. Press the Undo button within 5 seconds to revert.</div>` (announced once on entry)
- Once the card animates to height 0, set `aria-hidden="true"` and remove from focus order.

**Animation**:
- Collapse from full → 48 px: **400 ms**, ease-in-out. (Heavier easing so the user sees the transition, not just a snap.)
- Final collapse 48 px → 0: **200 ms** ease-in, fires only if Undo not clicked.
- Countdown bar fill: linear 5000 ms.

---

## 3.4 ESCALATED — sent to a higher-authority HR user

**Purpose**: HR can't make this call. The contradiction is forwarded to a Director (or another role with elevated permission) for resolution.

**Visual**:
- Severity badge swaps to a yellow `Escalated` pill.
- Both evidence panes remain visible but at `opacity-70` (still readable, not actionable).
- Action bar replaced by a single status line: "🔼 Escalated to Director Sophie Wilkes · 2026-06-03 14:22 · awaiting decision".
- A secondary text link "Rescind escalation" appears if `userRole === 'HR_LEAD' || userRole === 'ADMIN'`.

**Dimensions**: identical to IDLE.

**Tokens**:
- Escalated pill: `--badge-warning-bg` (#FFF4D6) text `--badge-warning-text` (#7A4A00)
- Rescind link: `--text-link`

**ARIA**:
- `aria-live="polite"` announcement: "Contradiction escalated to Director Sophie Wilkes."
- Evidence-pane buttons (citation jump, etc.) keep their focus but use `aria-disabled="true"` so the user understands they're informational.

**Animation**:
- Badge swap: cross-fade old badge → new badge over **200 ms**.
- Action bar: outgoing fade 200 ms + incoming status line slide-up 200 ms.

---

## 3.5 FROZEN — Pathway B2C asks HR to act before employee can continue

**Purpose**: The employee-side Pathway (B2C) is blocked on this contradiction. The employee sees a "waiting on your HR" message; the HR Resolution UI shows the same card with a frozen banner overlay so HR knows the case is gating downstream work.

**Visual changes from IDLE**:
- A top banner overlays the card header (does NOT replace it):
  - 32 px tall, full card width.
  - Background `--surface-warning-subtle` (#FFF8E1), text `--text-warning` (#7A4A00).
  - Icon ⏳ + copy: "Employee is waiting — they can't continue until you resolve this."
- Action bar unchanged but primary button colour pulses subtly to draw the eye:
  - Pulse: `--button-primary-bg` darkens by 5% over 800 ms, returns over 800 ms, loops while card is in FROZEN. Stops at `prefers-reduced-motion: reduce`.

**Dimensions**:
- Card grows by 32 px (banner pushes content down), no horizontal change.
- Other dimensions unchanged from IDLE.

**Tokens**:
- Banner background: `--surface-warning-subtle`
- Banner text: `--text-warning`
- Pulse animation uses `--button-primary-bg` with 5% darken via `color-mix(in oklab, var(--button-primary-bg) 95%, black)`

**ARIA**:
- Banner is rendered as a `role="alert"` region only on first entry (so AT announces once), then becomes `role="region" aria-label="Employee waiting"`.
- Live region: "Employee is waiting on this resolution to continue their pathway." — announce **once** on entry, **not** on re-render.

**Animation**:
- Banner slide-in from top: **200 ms** ease-out.
- Primary button pulse: continuous 1600 ms cycle while frozen. Stops cleanly when state transitions out.

**Coexistence**:
- FROZEN can coexist with LOADING (banner stays during the optimistic transition).
- FROZEN can coexist with ESCALATED (banner stays; the underlying card moves to ESCALATED visuals).
- FROZEN collapses to SUCCESS once the server confirms — banner animates out (200 ms slide-up) before card collapses.

---

## 3.6 ERROR — network or auth failure

**Purpose**: Server returned 5xx, 4xx (auth/permission), timeout (>3000 ms), or 409 conflict. UI rolls back the optimistic state and explains.

Three sub-variants surface different messaging:

| Sub-variant | Trigger | Message |
|---|---|---|
| `network` | fetch reject, offline | "Couldn't reach the server. Check your connection and try again." |
| `timeout` | >3000 ms no reply | "Still trying. Tap retry, or refresh the page." |
| `auth` | 401 / 403 | "Your session expired. Sign in to continue." → CTA: "Sign in" |
| `conflict` | 409 (someone else resolved this contradiction first) | "Someone else just resolved this. Refresh to see their decision." → CTA: "Refresh" |

**Visual changes from LOADING**:
- The "winning" pane's success ring removes; both panes return to opacity 1.
- Action bar replaces with an error pill (full-width) + a single retry/refresh/sign-in CTA + a "Dismiss" tertiary link.
- The error pill uses `--surface-error-subtle` background, `--text-error` text.

**Dimensions**: identical to IDLE.

**Tokens**:
- Error pill: `--surface-error-subtle` (#FDECEC) text `--text-error` (#7A0000)
- Primary action: `--button-primary-bg` (unchanged from idle); for `auth` variant, use `--button-warning-bg` (#A85C00 → white text) to distinguish.

**ARIA**:
- `role="alert"` on the error pill — fires AT announcement immediately.
- `aria-live="assertive"` for the message text.
- Focus moves to the retry/refresh/sign-in CTA on entry, with `tabIndex={-1}` set on the pill so it can hold focus programmatically.

**Animation**:
- Pane recovery (losing pane fades back, ring removed): **200 ms** ease-out.
- Error pill slide-in from below: **200 ms** ease-out.
- No pulse, no looping animation — error state stays still.

---

## 3.7 Timing budgets (summary)

| Transition | Duration | Easing | Token |
|---|---|---|---|
| Card mount fade-in | 100 ms | ease-out | `--motion-instant` |
| HIGH-severity badge pulse on mount | 400 ms × 2 | ease-in-out | `--motion-emphasis` |
| Optimistic checkmark scale-in | 100 ms | ease-out | `--motion-instant` |
| Losing pane fade-to-grayscale | 200 ms | ease-in-out | `--motion-quick` |
| Spinner rotation | 800 ms / cycle | linear | `--motion-spinner` |
| Server reply max budget | 2000 ms | — | n/a (UX SLO) |
| "Still saving…" hint trigger | 1500 ms | — | n/a |
| Timeout → ERROR trigger | 3000 ms | — | n/a |
| Card collapse to 48 px (SUCCESS) | 400 ms | ease-in-out | `--motion-emphasis` |
| Final collapse 48 px → 0 | 200 ms | ease-in | `--motion-quick` |
| Undo countdown bar fill | 5000 ms | linear | n/a |
| Badge cross-fade (ESCALATED) | 200 ms | ease-in-out | `--motion-quick` |
| FROZEN banner slide-in | 200 ms | ease-out | `--motion-quick` |
| FROZEN primary button pulse | 1600 ms / cycle | ease-in-out | `--motion-emphasis` |
| ERROR pill slide-in | 200 ms | ease-out | `--motion-quick` |

All durations honour `@media (prefers-reduced-motion: reduce)`: durations clamp to ≤ 50 ms, no continuous loops, no pulses.

---

## 4. Responsive behaviour

Three breakpoints map to the C1-11D layout system.

| Breakpoint | Card width | Evidence layout | Notes |
|---|---|---|---|
| `< 640 px` (mobile) | 100% | stacked vertically, full width each | Action bar buttons full-width, stacked vertically with `--space-2` gap |
| `640–1023 px` (tablet) | 100%, max 720 px | side-by-side at 50/50 | Buttons remain inline, smaller padding |
| `≥ 1024 px` (desktop) | max 840 px, centered | side-by-side at 50/50 | Default |

The header severity badge truncates the title at 1 line on mobile (with `text-overflow: ellipsis`). Tablet and desktop allow 2 lines.

---

## 5. Keyboard interaction map

| Key | Action |
|---|---|
| `Tab` | Cycles: Doc A pane → Doc A citation link → Doc B pane → Doc B citation link → Primary action → Secondary action → Tertiary action |
| `Shift+Tab` | Reverse |
| `Enter` / `Space` on a button | Activate (transition to LOADING) |
| `Enter` on a citation link | Open the OCR bbox citation (modal or side-panel — defer to global citation viewer pattern) |
| `Esc` while in LOADING | No-op (cannot cancel server resolution mid-flight) |
| `Esc` in SUCCESS during Undo window | Triggers Undo |
| `Esc` in ERROR | Triggers Dismiss |
| `Esc` in ESCALATED | No-op |

All focus rings use C1-11D `--ring-focus` (2 px solid `#0A56FF` with 1 px white inset). Never suppress focus indicators.

---

## 6. Permissions & visibility matrix

| Role | IDLE actions | Can escalate? | Can rescind escalation? |
|---|---|---|---|
| HR_VIEWER | view only — buttons disabled with tooltip "Read-only access" | no | no |
| HR_AGENT | Keep A, Keep B, Escalate | yes | no |
| HR_LEAD | Keep A, Keep B, Escalate | yes | yes |
| ADMIN | Keep A, Keep B, Escalate | yes | yes |
| EMPLOYEE | route returns 403 — component never renders | n/a | n/a |

For HR_VIEWER, the IDLE state still renders normally; only the action bar shows a disabled state with `aria-disabled="true"` and a tooltip on focus/hover.

---

## 7. Empty & boundary cases

| Scenario | Behaviour |
|---|---|
| Only one doc has an OCR snippet (e.g. one is hand-entered) | The hand-entered pane renders the typed value with a "Entered by HR · {user} · {date}" footer instead of a citation. No bbox link. |
| OCR confidence < 0.6 on either side | Show a `⚠ Low confidence` chip on that pane (uses `--badge-warning-bg`). Does not block resolution. |
| Both values agree after re-OCR (i.e. the contradiction was spurious) | Server returns 410 Gone; UI shows a one-line auto-resolve confirmation: "✓ Re-scan resolved this · values now agree." Card collapses without an Undo window. |
| Contradiction was deleted by the system (e.g. document withdrawn) | Same 410 Gone handling. |

---

## 8. Token reference (C1-11D)

This spec references the following tokens. Engineer should confirm they exist in `design/system/tokens.css` before implementation; if any are missing, file a sub-task against C1-11D.

```
Surfaces       : --surface-elevated · --surface-recessed · --surface-warning-subtle · --surface-error-subtle
Borders        : --border-subtle · --border-default · --border-success
Text           : --text-on-primary · --text-warning · --text-link · --text-error
Buttons        : --button-primary-bg · --button-secondary-bg · --button-warning-bg
Badges         : --badge-high-bg · --badge-high-text · --badge-mid-bg · --badge-low-bg
                 --badge-success-bg · --badge-success-text · --badge-warning-bg · --badge-warning-text
Motion         : --motion-instant (100ms) · --motion-quick (200ms) · --motion-emphasis (400ms) · --motion-spinner (800ms)
Spacing        : --space-2 (8px) · --space-3 (12px) · --space-4 (16px)
Radius         : --radius-md (8px) · --radius-lg (12px)
Shadow         : --shadow-md
Touch targets  : --touch-target-min (44px)
Focus          : --ring-focus
```

---

## 9. Testing checklist

- [ ] All 6 primary states render at correct dimensions on desktop, tablet, mobile.
- [ ] FROZEN overlay composes correctly with IDLE, LOADING, ESCALATED.
- [ ] Optimistic LOADING state rolls back cleanly on every ERROR sub-variant.
- [ ] Server reply at exactly 2000 ms shows the "Still saving…" hint at 1500 ms then proceeds.
- [ ] Timeout at 3001 ms transitions to ERROR (`timeout` variant).
- [ ] `prefers-reduced-motion: reduce` clamps all durations to ≤ 50 ms and disables pulse loops.
- [ ] HR_VIEWER role disables buttons with correct ARIA + tooltip.
- [ ] Keyboard tab order matches §5 in IDLE, LOADING, ESCALATED, FROZEN.
- [ ] Focus moves to retry CTA on ERROR entry.
- [ ] Live regions announce: optimistic save, escalation, error, success, FROZEN entry (once).
- [ ] Undo at 4900 ms succeeds; at 5100 ms is a no-op.
- [ ] Cross-fade transitions cause no visible "flash of unstyled text".

---

## 10. Out of scope (next tasks)

- **C1-12-be · Resolve + Escalate POST endpoints** (AIQ-570, currently in Validation) — server side of the optimistic flow.
- Visual mockups in Figma — this spec is a text+token handoff. If the engineer prefers Figma frames, that's a follow-up to C1-11D (the design system file).
- Mass-resolution UI (multiple contradictions at once) — explicitly out of MVP scope.
- Localization of strings — uses English copy throughout; FR/NO landing in Cohort 4 per the Pathway strings deferral.

---

*Spec generated 2026-06-03 by Claude Cowork via notion-task-executor + design:design-handoff.*
