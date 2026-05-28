# ReloPass Design System — v1

This is the source-of-truth design system for the HR Dashboard (Cohort 1) and any future ReloPass product surface that isn't marketing pages (which keep their own `--marketing-*` token family).

**Aesthetic register:** Linear / Stripe / Ramp — calm, precise, generous whitespace, subtle motion, no glass-morphism, no surface gradients (gradients only on illustrative accents).

**Coexistence rule:** the existing Antigravity component library at `frontend/src/components/antigravity/` is preserved. This seed adds the missing token families that Antigravity components and future shadcn primitives both consume. Nothing forks.

## Files in this directory

| File | Purpose |
|---|---|
| `tokens.css` | CSS custom properties — the single source of truth for color, spacing, type, radius, motion, shadow, z-index |
| `shadcn-theme.json` | Mapping from shadcn/ui's expected variable names to `--rp-*` tokens. Loaded when running `npx shadcn add <component>` |
| `README.md` | This file — component documentation and Do/Don't pairs |

## How to consume

```html
<!-- 1. Import tokens at the app root (replaces ad-hoc :root vars) -->
<link rel="stylesheet" href="/design/system/tokens.css">

<!-- 2. Reference tokens in component styles -->
<style>
  .my-card {
    background: var(--rp-surface);
    color: var(--rp-text-primary);
    padding: var(--rp-space-6);
    border-radius: var(--rp-radius-md);
    box-shadow: var(--rp-shadow-sm);
  }
</style>
```

In Tailwind classes (once the `_tailwind_extension_hint` in `shadcn-theme.json` is merged into `tailwind.config.js`):

```tsx
<div className="bg-background text-foreground p-6 rounded-md shadow-sm">
```

## Component inventory

| Component | Status | Antigravity file | Notes |
|---|---|---|---|
| Button | ✅ exists | `Button.tsx` + `LoadingButton.tsx` | Already in Antigravity. Refactor to consume `--rp-*` tokens. |
| Card | ✅ exists | `Card.tsx` | Already in Antigravity. Refactor to consume tokens. |
| Badge | ✅ exists | `Badge.tsx` | Already in Antigravity. Refactor to consume tokens. |
| Input | ✅ exists | `Input.tsx` | Already in Antigravity (not in C1-11D's required list but worth tokenising). |
| Select | ✅ exists | `Select.tsx` | Already in Antigravity. |
| Alert | ✅ exists | `Alert.tsx` | Already in Antigravity. |
| ProgressBar | ✅ exists | `ProgressBar.tsx` | Already in Antigravity. |
| Container | ✅ exists | `Container.tsx` | Already in Antigravity. |
| **Tag** | 🆕 new | — | Needed for case-status chips on the HR Dashboard table. Differs from Badge: Tag is interactive (filter-clickable), Badge is presentational. |
| **Tooltip** | 🆕 new | — | Needed for table-cell truncation reveals + icon-button labels. shadcn primitive recommended. |
| **Dialog** | 🆕 new | — | Modal confirmation for destructive actions (delete case, override extraction). shadcn primitive recommended. |
| **Sheet** | 🆕 new | — | Right-side drawer for the bbox PDF viewer (C1-11d). shadcn primitive recommended. |
| **Tabs** | 🆕 new | — | Case detail panel section switcher (employee / family / documents / contradictions). shadcn primitive recommended. |
| **Table** | 🆕 new | — | Case-list table with sort/filter chrome. Build custom (shadcn Table is basic; HR Dashboard needs sticky headers + virtualisation). |
| **EmptyState** | 🆕 new | — | "No cases yet" / "No contradictions to review" — repeated pattern across the dashboard. |

The 7 🆕 components are the C1-11 implementation backlog after this seed lands.

---

## Component documentation

### Button

**Use when** the user takes a discrete action — submitting a form, opening a dialog, navigating to a related view, confirming/cancelling a destructive change.

**Variants**

| Variant | Use when |
|---|---|
| `primary` | The single most important action on the page (form submit, "Create case"). One per view. |
| `secondary` | Supporting actions adjacent to primary ("Cancel", "Save draft", "Export") |
| `ghost` | Tertiary actions inside cards/tables ("Edit", "Remove row") — minimal visual weight |
| `destructive` | Irreversible actions (delete, terminate, reject) — always pair with a Dialog confirmation |

**Sizes:** `sm` (28px height, in table rows), `md` (36px, default), `lg` (44px, hero CTAs — rare in HR Dashboard).

**States:** default, hover, focus (always with `--rp-shadow-focus` ring), active, disabled, loading (LoadingButton for async actions).

**Tokens used:**
- Color: `--rp-color-primary-600` (primary bg), `--rp-color-neutral-200` (secondary border), `--rp-color-danger-500` (destructive bg)
- Spacing: `--rp-space-3` (md horiz padding), `--rp-space-2` (gap to icon)
- Radius: `--rp-radius-md`
- Motion: `--rp-duration-fast` for hover, `--rp-easing-out`

**Accessibility:** native `<button>` element. `aria-busy="true"` while loading. Loading state must not disable the button — it must remain focusable so screen reader users can hear the state change.

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use exactly one `primary` per view | Stack two `primary` buttons side-by-side (creates competing CTAs) |
| Use `destructive` + confirmation Dialog for irreversible actions | Use `destructive` for "Cancel" — it suggests irreversibility |
| Pair icon + text label for primary/secondary | Use icon-only buttons without an `aria-label` |
| Use `LoadingButton` for async actions, with visible spinner | Replace the button with a separate spinner (loses focus context) |

---

### Card

**Use when** grouping related information into a visually distinct surface — a single case summary, a document preview, a metric tile.

**Variants**

| Variant | Use when |
|---|---|
| `default` | Standard surface for grouped content |
| `elevated` | Floating cards (e.g. command palette result rows) — adds `--rp-shadow-md` |
| `interactive` | Clickable cards that navigate (whole-card click target) — adds hover state |

**States:** default, hover (only on `interactive`), focus-within (when card contains a focused element).

**Tokens used:** `--rp-surface`, `--rp-border-default`, `--rp-radius-md`, `--rp-space-6` (padding), `--rp-shadow-sm` (rest), `--rp-shadow-md` (interactive hover).

**Accessibility:** if `interactive`, the entire card becomes a `<a>` or `<button>` — never wrap a card with an interactive parent if it already contains buttons (nested interactive elements break keyboard nav).

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use `--rp-space-6` as the default internal padding | Use ad-hoc spacing per card (loses rhythm) |
| Use `interactive` variant for whole-card navigation | Add a "View" button inside an `interactive` card |
| Group related metadata in nested rows with `--rp-space-3` gap | Stack 6+ data points in one card (use a Table instead) |

---

### Badge

**Use when** marking a presentational status that the user CANNOT interact with — case status ("Active", "Pending"), document type ("Passport"), severity ("WARN").

(For interactive status chips that filter or navigate, use **Tag**.)

**Variants**

| Variant | Use when |
|---|---|
| `info` | Neutral informational marker (default) |
| `success` | Positive states (Active, Confirmed, Passed) |
| `warning` | Attention required (Expires Soon, Needs Review) |
| `danger` | Critical states (Expired, Failed, Blocked) |
| `neutral` | Inert metadata (document type, count) |

**Sizes:** `sm` (20px height, in table cells), `md` (24px, default).

**Tokens used:** `--rp-status-*-bg` + `--rp-status-*-fg` pairs, `--rp-radius-sm`, `--rp-text-xs` (sm) or `--rp-text-sm` (md), `--rp-weight-medium`, `--rp-tracking-wide` for uppercase variants.

**Accessibility:** the badge text MUST be self-describing — never rely on color alone. ❌ a red badge with no text means "Expired" only to sighted users; ✅ a red badge with "EXPIRED" text is accessible.

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use semantic variant matching the meaning ("danger" for Expired) | Use `info` for everything and rely on text colour |
| Keep text under 12 characters | Use Badge for full sentences (use Alert instead) |
| Self-describe via text content | Rely on colour as the only signal |

---

### Tag (🆕 new)

**Use when** the user can click a status chip to filter, search, or navigate. Visually similar to Badge but always interactive.

**Variants:** same color set as Badge (info/success/warning/danger/neutral) plus a `dismissible` modifier that adds an "x" button (used in active-filter chips).

**States:** default, hover (background darkens one step), active, focus, dismissed (slide-out animation, `--rp-duration-fast`).

**Accessibility:** `<button>` element. If `dismissible`, the "x" button has its own `aria-label` ("Remove filter: Active cases"). Tag itself has `aria-pressed` when used as a toggle filter.

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use for clickable filters above tables | Use Tag for presentational status (use Badge) |
| Always include an aria-label on the dismiss button | Leave the dismiss button as a bare "×" character |

---

### Tooltip (🆕 new)

**Use when** revealing supplementary information on hover/focus that doesn't need to be permanently visible — full text of a truncated table cell, the meaning of an icon-only button, the keyboard shortcut for an action.

**Behaviour:**
- Appears after a 400ms hover delay (`--rp-duration-slower`); appears immediately on keyboard focus
- Dismisses on mouse leave / blur / Escape key
- Positions itself to remain on-screen (top/bottom/left/right inferred from viewport)

**Tokens used:** `--rp-surface-inverse` (dark background), `--rp-text-inverse`, `--rp-text-sm`, `--rp-radius-sm`, `--rp-shadow-md`, `--rp-z-tooltip`, `--rp-duration-fast` (fade-in), `--rp-easing-out`.

**Accessibility:** the trigger element MUST also be focusable. The tooltip is announced via `aria-describedby` so screen readers read it on focus. NEVER put interactive content (buttons, links) inside a tooltip — use a Popover for that.

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use for truncation reveal + icon-only button labels | Use for instructional copy that the user needs (put it in the UI directly) |
| Keep text under 1 line in most viewports | Put buttons or links inside a tooltip |
| Honour `prefers-reduced-motion` (tokens.css does this) | Show a tooltip on a focus event after a key press without keyboard nav (false positive) |

---

### Dialog (🆕 new)

**Use when** the user must explicitly confirm or input something before the workflow continues — confirmations for destructive actions, multi-field forms that warrant focus, system-blocking errors.

**Structure:**
- Scrim (`--rp-color-neutral-900` @ 50% opacity) fades in over `--rp-duration-base`
- Dialog panel slides up from below + fades in over `--rp-duration-slow`
- Focus moves into the dialog on open; trap focus inside; restore focus to trigger on close
- Escape key closes; clicking scrim closes UNLESS the dialog has unsaved changes (then prompt with secondary Dialog)

**Sizes:** `sm` (320px, confirmations), `md` (480px, default forms), `lg` (640px, multi-section), `full` (90vw, rare — bbox PDF viewer uses Sheet instead).

**Tokens used:** `--rp-surface`, `--rp-radius-lg`, `--rp-shadow-lg`, `--rp-z-dialog`, `--rp-space-6` (panel padding), `--rp-space-4` (between header/content/actions).

**Accessibility:** `role="dialog"` + `aria-labelledby` pointing at the dialog title. Focus must trap inside. The trigger button MUST receive focus back on close.

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Always require explicit Cancel/Confirm — no auto-dismiss for destructive | Stack dialogs more than 2 deep (cognitive overload) |
| Use `sm` size for simple yes/no confirmations | Use Dialog as a permanent UI panel (use Sheet instead) |
| Confirm before closing if form has unsaved changes | Close on scrim-click when destructive action is pending |

---

### Sheet (🆕 new)

**Use when** displaying a contextually-related panel alongside the main content — the bbox PDF viewer for an extracted document, the case-history timeline, an inline detail expansion.

**Variants:** `right` (default, used for PDF viewer per C1-11d), `bottom` (mobile case detail), `left` (rare).

**Width:** `sm` (320px), `md` (480px), `lg` (640px, default for PDF viewer), `xl` (820px).

**Behaviour:**
- Slides in from the assigned edge over `--rp-duration-slow` with `--rp-easing-out`
- Background content does NOT scroll-lock (Sheet is non-blocking by default — distinguishes from Dialog)
- An optional `scrim` mode adds a scrim for cases where the Sheet IS blocking
- Escape closes; clicking outside closes; resize-handle on the inner edge for `lg`/`xl` widths

**Tokens used:** `--rp-surface`, `--rp-shadow-lg`, `--rp-z-dialog` (with scrim) or `--rp-z-dropdown` (without), `--rp-border-default` (inner edge separator).

**Accessibility:** `role="dialog"` + `aria-labelledby`. Focus moves in on open. Unlike Dialog, focus does NOT trap unless `scrim` is enabled (Sheet without scrim is a side panel, not a modal).

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use for contextual side-by-side detail (PDF viewer, history) | Use for confirmations (use Dialog) |
| Default to non-scrim — Sheet should not block the main flow | Stack two Sheets simultaneously (only one Sheet at a time) |
| Provide a visible close button in addition to Escape | Make the sheet so wide it covers >70% of viewport (use full Dialog instead) |

---

### Tabs (🆕 new)

**Use when** switching between mutually-exclusive content panels within the same context — case detail's "Employee / Family / Documents / Contradictions" sections.

**Variants**

| Variant | Use when |
|---|---|
| `default` | Underline-style tabs (sits above content, underline animates) — primary use case |
| `pills` | Pill-style segmented control — for compact filter-style switches |
| `vertical` | Left-rail tabs — settings pages, rare in HR Dashboard |

**States:** default, hover, active (current tab), focus.

**Tokens used:** `--rp-text-secondary` (inactive), `--rp-text-primary` (active), `--rp-color-primary-600` (underline / pill fill for active), `--rp-text-sm`, `--rp-weight-medium`, `--rp-space-2` to `--rp-space-4` (padding), `--rp-duration-base` (underline transition), `--rp-easing-in-out`.

**Accessibility:** `role="tablist"` + `role="tab"` + `role="tabpanel"`. Arrow-key navigation between tabs; Home/End jump to first/last. Active tab has `aria-selected="true"`. Tab panels are revealed/hidden, not destroyed (preserves user state).

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use for 2–6 mutually-exclusive panels | Use for navigation that loads different routes (use a Nav component) |
| Make the active tab visually distinct (underline + bold) | Rely on color alone to indicate active |
| Preserve form state across tab switches | Destroy tab panel content on switch (loses state) |

---

### Table (🆕 new)

**Use when** displaying rows of structured data with multiple sortable/filterable columns — the case list is the canonical example.

**Sub-components:** TableHeader (sticky on scroll), TableRow (with optional hover and selection states), TableCell (with truncation + Tooltip on overflow).

**Features required:** column sort (single-column at a time), column filter (chip-list above table using Tag components), row selection (checkbox column), sticky header on scroll, row hover, click-to-navigate (whole-row interactive variant), empty state (use EmptyState component when 0 rows match).

**Densities:** `comfortable` (44px row height, default), `compact` (32px, for dense dashboards).

**Tokens used:** `--rp-surface` (rows), `--rp-surface-subtle` (alt rows on `striped` mode), `--rp-border-subtle` (row dividers), `--rp-space-3` (cell vertical padding compact) / `--rp-space-4` (cell vertical padding comfortable), `--rp-text-sm`, `--rp-z-sticky` (sticky header).

**Accessibility:** `<table>` element with `<thead>` + `<tbody>` + proper `<th scope="col">`. Sort buttons have `aria-sort="ascending"|"descending"|"none"`. Selection checkboxes have an explicit `aria-label` ("Select row 3 of 47, case CASE-2027-0142").

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Use for tabular data with sort/filter needs | Use for 2-column key-value displays (use a definition list instead) |
| Sticky-header on vertical scroll | Make rows so dense that touch targets fall below 32px |
| Single-sort (clicking column sort clears others) | Allow multi-column sort by default (users find this confusing) |
| Pair empty state with the EmptyState component | Show a blank white area when 0 rows match |

---

### EmptyState (🆕 new)

**Use when** a container has no content yet — initial state ("No cases yet — create your first"), filter zero-match state ("No cases match these filters"), success/cleared state ("All caught up — no contradictions to review").

**Structure:**
- Centered illustration or icon (96×96px, optional)
- Headline (`--rp-text-lg`, `--rp-weight-semibold`)
- Description (1–2 sentences, `--rp-text-sm`, `--rp-text-secondary`)
- Optional primary action button

**Variants**

| Variant | Use when |
|---|---|
| `initial` | First-time-user state ("Get started by adding...") — includes primary action |
| `cleared` | Empty because the user resolved everything ("All caught up") — celebratory, no primary action |
| `filtered` | Filters returned zero results ("No cases match") — secondary action to clear filters |
| `error` | Container errored loading ("Couldn't load cases") — primary action to retry |

**Tokens used:** `--rp-space-8` (vertical padding), `--rp-text-secondary` (description), `--rp-text-tertiary` (when even more muted is wanted), `--rp-color-neutral-300` (icon stroke).

**Accessibility:** the empty state container has `role="status"` so screen readers announce the state change when filters update.

**Do / Don't**

| ✅ Do | ❌ Don't |
|---|---|
| Always tell the user WHY it's empty and WHAT to do next | Show a generic "No data" message |
| Use the `cleared` variant — quiet success — when user resolved everything | Add a fake "create" button on a `cleared` state (loses the celebration) |
| Use a relevant illustration, not a generic empty-box | Use a celebratory illustration on an error state |

---

## What's intentionally NOT in this seed

- **Toast / Notification** — needed for transient feedback (autosave confirmations, errors). Add in v2; depends on a notification-channel decision (top-right stack vs bottom inline).
- **Avatar** — needed when employee photos surface. Add when the photo-PHI handling is wired up.
- **Command palette** — Linear-style keyboard-driven action search. Worth adding in v2 once the action vocabulary is stable.
- **Skeleton loaders** — replace ad-hoc loading spinners across the dashboard. Worth a v2 follow-up.
- **DataTable virtualisation** — needed when case-list rows exceed ~500. The base Table component above will need a virtual-scroll wrapper.

These are intentional follow-ups, not gaps.

## How to add a new shadcn primitive

```bash
# 1. From repo root, with shadcn-theme.json in place
npx shadcn@latest add dialog

# 2. The generated component will reference shadcn's expected CSS vars
#    (--background, --foreground, etc.) — these are mapped to --rp-* tokens
#    via the cssVars block in shadcn-theme.json + tailwind.config.js

# 3. Verify the generated component imports from frontend/src/components/ui/
#    (shadcn convention) and reorganise if you want it adjacent to antigravity:
#    consider moving to frontend/src/components/antigravity-ext/dialog.tsx
#    so the Antigravity + shadcn merger has a clear convention.

# 4. Refactor or wrap as needed to match the documented Do/Don'ts above.
```

## Migration notes for existing Antigravity components

Each of Button/Card/Badge/Input/Select/Alert/ProgressBar/Container should:

1. Replace hardcoded color values with `var(--rp-*)` tokens.
2. Replace hardcoded spacing (e.g. `padding: 16px`) with `var(--rp-space-4)`.
3. Replace ad-hoc border-radius with `var(--rp-radius-md)` (or smaller for Tags/Badges).
4. Add focus-ring via `box-shadow: var(--rp-shadow-focus)` instead of `outline`.
5. Wrap transitions in `var(--rp-duration-*)` + `var(--rp-easing-*)`.

This refactor is the responsibility of the C1-11 implementation task — not this seed.

## Validation

Run `design:design-system audit` against this directory + `frontend/src/components/antigravity/` to verify:
- Tokens are used consistently (no hardcoded hex / px values in component files)
- Each component has all 5 sections: variants, states, tokens, a11y, do/don't
- Naming is consistent (semantic tokens preferred over scale tokens in component code)

The audit may flag the 7 🆕 components as missing implementation — that's expected and tracked as the C1-11 implementation backlog.

---

*v1 — light theme only. Dark theme tokens land in `tokens-dark.css` when the dark mode work begins.*
