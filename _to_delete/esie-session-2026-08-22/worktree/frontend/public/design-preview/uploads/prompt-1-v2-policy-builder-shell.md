# PROMPT 1 (v2) — HR Policy Builder: Page Shell, Two Modes & Template Selection

## What you are building

A redesigned **Policy Builder** page inside the ReloPass HR portal at `/hr/policy-builder`. The guiding principle of this design is: **HR should never face a blank field**. Every value is pre-filled from a template. HR's job is to review and adjust, not to know what number to type.

The page has two distinct operating modes that HR switches between:

- **Configure mode** — guided, one tier at a time, one benefit at a time. Used when setting up a policy for the first time or restructuring it from scratch. (Covered in depth in Prompts 2a.)
- **Adjust mode** — a compact accordion list for ongoing edits after the policy is live. (Covered in Prompt 2b.)

This prompt covers the page shell, the mode switcher, the three-template picker, the header, the floating changes tray, and the transitions between modes.

---

## Tech stack & design system

- **Framework**: React 18 + TypeScript, Vite, TailwindCSS
- **Design system**: `frontend/src/components/antigravity/` — Button, Card, Badge, Modal, Tabs, Tooltip, Alert. Use these exclusively; no external UI libraries.
- **Route**: `/hr/policy-builder`
- **State**: Feature-scoped React context (`PolicyBuilderContext`). No global store.
- **Auto-save**: Debounced `PUT /api/hr/policy-config/draft` every 20 seconds when there are unsaved changes.

---

## Page header

Fixed, 56px tall. Two visual states:

### Header — no policy exists yet (first visit)

```
[ Policy Builder ]   [ NO POLICY ]          [  Build from template  |  Import from document  ]
```

- "NO POLICY" is a grey badge. No save/publish buttons yet.
- The two CTAs are the only interactive elements — they dominate the header.

### Header — draft or published policy exists

```
[ Policy Builder ]  [ DRAFT · Saved 5s ago ]     [ Configure | Adjust ]    [ Save draft ]  [ Preview ]  [ ● Publish ]
```

Left to right:
- **Title** "Policy Builder" H2
- **Status badge**: `DRAFT` (amber) or `PUBLISHED v2.1 · Effective 1 Jun 2026` (green). If draft differs from published: show "DRAFT · X changes" where X is the count of changes from the published version.
- **Mode switcher** (center): A two-segment pill control — `Configure` | `Adjust`. This is the primary navigation element. Switching modes never loses data.
- **Right actions**: `Save draft` (secondary), `Preview` (ghost, opens employee-facing view in a modal), `Publish` (primary, dark). Publish is disabled until validation passes.
- **Version history** icon button (clock) at the far right — opens a right-side drawer listing prior versions with dates and change counts.

---

## Three templates — the starting point

### When to show the template picker

Show the template picker **only on first visit** (when `GET /api/hr/policy-config` returns no existing config). It appears as a full-screen modal overlay — not a page, a modal — so HR can dismiss it and start from scratch if they prefer.

After a template is applied, the picker is accessible again via a `Change template` link in a secondary position (e.g. inside the version history drawer or a `···` overflow menu). Re-applying a template resets everything to baseline and requires a confirmation: "This will reset all customisations. Your current draft will be saved as a version before resetting."

### Template picker modal

Modal width ~760px, centred. Header: "Pick a starting point" with subtitle "You can customise every detail after applying — this is just the baseline."

Three template cards arranged in a row (or 2+1 on narrow screens). Each card:

```
┌─────────────────────────────────┐
│  🛡️                             │
│  Essential                      │
│                                 │
│  Core benefits only. Tight      │
│  caps at the lower market       │
│  quartile. Good for companies   │
│  new to international mobility. │
│                                 │
│  Covers: 18 of 31 benefits      │
│  Est. annual cost: €8,000–12,000│
│                                 │
│  [ Use Essential ]              │
└─────────────────────────────────┘
```

**Card 1 — 🛡️ Essential**
- Tagline: "Core benefits only. Tight caps, no discretionary allowances."
- Covers: 18 of 31 benefits (the mandatory and near-mandatory ones)
- Pre-filled amounts at lower-quartile market rates
- Good for: companies doing their first policy, or companies with infrequent relocations

**Card 2 — ⚖️ Standard** (visually highlighted as "Most common")
- Tagline: "The most common setup across ReloPass companies. Balanced caps at market median."
- Covers: 26 of 31 benefits
- Pre-filled amounts at market median rates
- Good for: most companies as a starting point

**Card 3 — 🚀 Generous**
- Tagline: "Full benefit suite with competitive caps. Used to attract senior international talent."
- Covers: 31 of 31 benefits
- Pre-filled amounts at upper-quartile market rates
- Good for: companies competing for senior hires across borders, or mature mobility programmes

Each card shows a subtle visual encoding of generosity: Essential has a compact, minimal layout; Standard is balanced; Generous has a slightly richer feel (more line items visible as a teaser list).

### After template selection

1. Call `POST /api/hr/policy-config/draft/apply-template` with `{ template_key: "essential" | "standard" | "generous" }`.
2. Close the modal with a smooth fade.
3. **Immediately enter Configure mode** — do not show the full benefit grid. The user lands on the Configure mode tier selection screen (Prompt 2a).
4. Show a brief toast: "Standard template applied — 26 benefits pre-filled. Let's configure your first tier."

---

## Configure mode entry point — Tier selection screen

This is the first screen HR sees after applying a template (or when switching to Configure mode on an existing policy).

### Layout

A clean, centred screen (not full-width canvas). ~580px wide, vertically centred in the content area.

### Header of the screen (inside the content area, below the page header)

```
Configure your policy  ›  [Select a tier]
```

Breadcrumb-style progress indicator. As HR progresses into a tier it becomes:
```
Configure your policy  ›  Manager  ›  Housing & relocation  ›  Benefit 3 of 7
```

### Tier cards

Display all configured tiers as cards in a vertical stack (not a horizontal grid — this is sequential, not comparative). Each tier card:

```
┌──────────────────────────────────────────────────────────┐
│  ● Manager                                        →      │
│  Long-term · Permanent · Any family status               │
│  26 benefits configured · 0 reviewed                     │
└──────────────────────────────────────────────────────────┘
```

Status indicators per tier:
- **Not started**: grey dot, "0 reviewed"
- **In progress**: amber dot, "12 of 26 reviewed"
- **Complete**: green dot, "All reviewed ✓"

HR clicks a tier card to enter Configure mode for that tier (see Prompt 2a). They can return to this screen at any time via the breadcrumb.

### Add tier button

Below the tier cards: `+ Add another tier` — opens a compact inline form (not a drawer): tier name field + 3 targeting axis selects (employee level, assignment type, family status). Adds the tier to the list without leaving the screen.

### Bottom CTA

Once at least one tier is complete: `Ready to publish? →` button (primary, appears only when ≥1 tier is complete). Clicking runs validation and either shows errors or opens the publish confirmation.

---

## Adjust mode entry point

When switching to Adjust mode (via the mode pill in the header), the content area transitions to the accordion list (Prompt 2b). The transition is a smooth cross-fade, not a page reload.

The tier selection screen from Configure mode is replaced by a **tier tab row** at the top of the accordion — a horizontal tab bar showing all tier names. HR clicks a tab to view/edit that tier's benefits in the accordion.

---

## Floating changes tray

This is a persistent element that appears as soon as HR makes any change that differs from the template baseline (or from the published version if one exists).

### Appearance

A small pill/badge anchored to the bottom-right of the viewport (above the scrollbar, z-index above the content):

```
  ⬦ 5 changes from Standard  ›
```

- Icon: a small delta/diamond symbol
- Text: "N changes from [template name]" or "N changes from published" (whichever is more recent baseline)
- Arrow: indicates it's clickable
- Color: amber background when changes exist, green when 0 changes

### Tray panel

Clicking the badge opens a slide-up panel from the bottom (~320px tall, full width). The panel lists every change:

```
┌──────────────────────────────────────────────────────────────┐
│  5 changes from Standard template        [Revert all]  [×]  │
├──────────────────────────────────────────────────────────────┤
│  Host housing cap · Manager                                  │
│  €2,000/mo  →  €2,500/mo                     [Revert]       │
│                                                              │
│  Language training · Director                                │
│  Excluded  →  €300 one-time                  [Revert]       │
│                                                              │
│  Tax equalisation · Manager                                  │
│  Excluded  →  Included                       [Revert]       │
│                                                              │
│  Relocation allowance · VP                                   │
│  €1,500  →  €2,000                           [Revert]       │
│                                                              │
│  Storage · Manager                                           │
│  Included  →  Excluded                       [Revert]       │
└──────────────────────────────────────────────────────────────┘
```

Each row shows: benefit name · tier · old value → new value · [Revert] button.

Revert calls `POST /api/hr/policy-config/draft/revert-row` with `{ benefit_key, targeting_signature }`.

"Revert all" shows a confirmation before resetting the entire draft to the template baseline.

---

## Validation before publish

Before enabling the Publish button, check:
- At least one tier exists with at least one covered benefit
- No two tiers have identical targeting (same assignment_type + family_status + employee_level combination)
- All tiers have a name
- All currency-type covered benefits have a non-zero amount

Validation errors appear in a compact panel just above the Publish button (not a modal, inline). Each error is a link that navigates to the offending tier/benefit.

The Publish flow: HR clicks Publish → modal asks for `effective_date` (date picker, defaults to today + 7 days) and optional `policy_version` label → confirm → `POST /api/hr/policy-config/publish`.

---

## API connections for this prompt

| Purpose | Endpoint |
|---|---|
| Load existing config | `GET /api/hr/policy-config` |
| Ensure draft exists | `POST /api/hr/policy-config/draft` |
| List templates | `GET /api/hr/policy-config/templates` |
| Apply template | `POST /api/hr/policy-config/draft/apply-template` |
| Save draft | `PUT /api/hr/policy-config/draft` |
| Revert a single row | `POST /api/hr/policy-config/draft/revert-row` |
| Version history | `GET /api/hr/policy-config/history` |
| Publish | `POST /api/hr/policy-config/publish` |
| Diff vs published/template | `GET /api/hr/policy-config/diff` |

---

## Key constraints

- Switching between Configure and Adjust mode must never trigger a page reload. It's a client-side state switch.
- The floating changes tray must never obscure primary action buttons (Save draft, Publish). On small screens, tuck it to the left if buttons are on the right.
- Auto-save indicator ("Saving…" / "Saved 5s ago") is displayed as a small muted label in the header status area — not a toast, not intrusive.
- The entire Configure mode flow (Prompt 2a) operates without ever showing the full benefit grid. If HR wants to see everything at once, they switch to Adjust mode.
