# PROMPT 2b — Adjust Mode: Accordion List with Change Tracking

## Context

This prompt is part of the ReloPass HR Policy Builder. Prompt 1 (v2) covers the shell. Prompt 2a covers Configure mode. This prompt covers **Adjust mode** — the compact editing surface HR uses after the initial policy is configured and published, for ongoing fine-tuning.

Adjust mode is the default mode after a policy is published. It gives HR a scannable overview of the entire policy, with inline editing, visible change indicators, and advanced options accessible on demand.

---

## Tech stack

- React 18 + TypeScript, TailwindCSS
- Design system: `frontend/src/components/antigravity/`
- State: `PolicyBuilderContext` (Prompt 1 v2)
- Route: `/hr/policy-builder` — Adjust mode is a content-area state, not a separate route

---

## Layout overview

```
[ Tier tabs: Manager | Director | VP | + Add tier ]
─────────────────────────────────────────────────────
[ Category 1: Pre-assignment support  ↓ ]   [  5  ]
[ Category 2: Relocation assistance   ↓ ]   [  7  ]   ← one open at a time
[ Category 3: Compensation & allow.   ↓ ]   [  8  ]
[ Category 4: Family & education      ↓ ]   [  2  ]
[ Category 5: Leave & repatriation    ↓ ]   [  5  ]
[ Category 6: Tax & payroll           ↓ ]   [  4  ]
─────────────────────────────────────────────────────
                            [ ⬦ 5 changes ]  (tray)
```

The layout is strictly vertical. No horizontal tier grid. Tiers are selected via tabs at the top. One category accordion open at a time.

---

## Tier tabs

A horizontal tab bar at the top of the content area (below the page header):

```
[ Manager · 19 covered ] [ Director · 24 covered ] [ VP · 31 covered ] [ + Add tier ]
```

Each tab shows the tier name + count of covered benefits. The active tab has an underline indicator.

Clicking a tab switches the accordion content to show that tier's configuration. The switch is instant (client-side state, no API call) since the full draft is already loaded.

`+ Add tier` opens a compact inline panel below the tab bar (not a drawer, not a modal) — just a small card with: tier name input + 3 targeting axis selects (employee level, assignment type, family status) + `Add tier` / `Cancel` buttons. On add, the new tier tab appears and is auto-selected, with all benefits pre-filled from the template baseline for that tier.

---

## Category accordion rows

Each of the 6 category sections is a collapsible accordion row:

### Collapsed state

```
▶  RELOCATION ASSISTANCE                                        7 benefits · €18,500 est.
```

- Chevron (▶ collapsed, ▼ expanded) on the left
- Category name in small caps
- Right-aligned: benefit count + estimated annual cost for the active tier
- If any benefit in the category has been changed from the template: show a small amber `⬦ N changed` badge on the right side of the row

Click anywhere on the row to expand. Expanding one section collapses all others (one open at a time).

### Expanded state

The section expands to show all benefit rows within that category. Section header remains sticky while scrolling through the rows.

---

## Benefit row (the core element of Adjust mode)

Each benefit is a single horizontal row. Maximum information density: one row per benefit, nothing more. Design for a 1280px wide screen — the row should be comfortable at that width.

### Row anatomy

```
[ ○/● ] [ Benefit name                    ] [ €  2,500  ] [ / MO  ▼ ] [ ⬦ was €2,000 ] [ ··· ]
```

Left to right:

**1. Coverage toggle (leftmost)**
A pill toggle: filled green dot (●) = Covered, empty circle (○) = Excluded. Clicking toggles coverage. If switching from Covered to Excluded, show a 1-line inline confirmation in the row: "Exclude [Name] for [Tier]? [Confirm] [Cancel]" — do not open a modal.

**2. Benefit name**
Regular weight, 14px. No truncation — wrap if needed (though all 31 standard names fit in ~260px). Clicking the name opens the Adjust panel (same as in Configure mode, but as an inline expand below this row rather than a separate card). See "Adjust panel" section below.

**3. Amount input**
A clean number input field, ~80px wide, right-aligned number. Shows the current value. Directly editable — HR can click and type a new value. The field has no visible border at rest; shows a border on focus.

If `value_type` is `text` (e.g. "As per host country norms"), show the text value truncated to ~20 chars. Click to edit inline.

If `value_type` is `none` or the benefit is excluded, the input is greyed out and non-interactive.

**4. Frequency selector**
A compact dropdown (~80px): ONE-TIME / /MO / /YR / /TRIP / /DAY / /DEP / CUSTOM. Shows abbreviated labels. Full labels appear in the dropdown options.

**5. Change indicator (conditional)**
Only visible if this benefit's value differs from the template baseline or published version. Shows as:
```
⬦ was €2,000
```
Small amber text, ~100px. The `⬦` icon is the delta/change symbol. On hover, show a tooltip: "Changed from Standard template default (€2,000/mo). Click to revert." Clicking the indicator reverts this single row (calls `POST /api/hr/policy-config/draft/revert-row`).

**6. Row overflow menu (`···`)**
Appears on row hover. Options:
- `Edit advanced settings` → expands the Adjust panel (same as clicking the benefit name)
- `Revert to template default` → reverts this row (with confirmation if it's the only change)
- `Copy to other tiers` → opens a mini picker: which tiers should get this same value?

---

## Row states

**Standard (covered, unchanged):**
```
●  Host housing cap                    €  2,500    / MO  ▼
```

**Covered + changed from template:**
```
●  Host housing cap                    €  3,200    / MO  ▼     ⬦ was €2,500
```

**Excluded:**
```
○  Host housing cap                              —                              (greyed out)
```

**Excluded + changed (was covered):**
```
○  Host housing cap                              —                ⬦ was €2,500/mo
```

**Pending (no decision yet — only in a newly-added tier):**
```
?  Host housing cap                       [Set value]             (amber left border)
```

---

## Inline Adjust panel

When HR clicks a benefit name or "Edit advanced settings" in the row overflow menu, an expand panel slides down directly below that row (not a drawer, not a modal). Other rows remain visible above and below — this is inline editing, not a full-screen takeover.

The panel is ~400px tall when expanded, showing:

```
┌── Adjust: Host housing cap · Manager ───────────────────────────────────────────────┐
│                                                                                      │
│  Coverage:   [● Covered]  [○ Excluded]  [○ Optional — employee chooses]             │
│                                                                                      │
│  Value type: [● Fixed amount €]  [○ % of base salary]  [○ Text / policy note]      │
│                                                                                      │
│  Amount:  €  [  2,500  ]   /   [ Monthly ▼ ]                                        │
│                                                                                      │
│  Cap rule:   [ ] Apply a spending cap                                                │
│              (if checked expands: Cap at €[___] / [period]. Exceeds cap: [▼])       │
│                                                                                      │
│  Conditions: (optional — restrict when this applies within the tier)                 │
│  [ ] Only if assignment type is: [long_term ▼]                                      │
│  [ ] Only if family status is:   [accompanied_family ▼]                             │
│  [ ] Only if assignment > [  ] months                                               │
│                                                                                      │
│  Jurisdiction overrides:  [ + Add country override ]                                │
│  🇩🇪 Germany: €3,200/mo  (overrides base)                   [Remove]               │
│                                                                                      │
│  Internal notes: [________________________________________________]                  │
│                                                                                      │
│  [ Save ]    [ Cancel ]    ⬦ was €2,500 · [Revert to template]                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

All fields are pre-filled. The revert link at the bottom of the panel is a shortcut.

Saving calls `PUT /api/hr/policy-config/draft` (debounced with the rest of the draft). The panel closes automatically on save.

---

## Category footer (visible at the bottom of each open section)

After all benefit rows in a section, show a thin footer row:

```
  + Add custom benefit                            Category subtotal: €18,500 est./yr
```

- "+ Add custom benefit" opens a compact inline form at the bottom of the section: benefit name input + value type + amount. Custom benefits get a `custom_` prefix key.
- Category subtotal: sum of covered, currency-type benefits in this category, annualised for the active tier.

---

## Tier summary bar (bottom of the page, outside the accordion)

A persistent summary section below all 6 category accordions, always visible (no accordion collapse):

```
┌──────────────────────────────────────────────────────────────────┐
│  Manager tier — estimated annual cost                            │
│                                                                  │
│  One-time:  €12,400    Monthly:  €3,200/mo    Annual est:  €51k │
│                                                                  │
│  19 covered  ·  5 excluded  ·  2 optional                        │
└──────────────────────────────────────────────────────────────────┘
```

This updates in real time as HR edits values. Uses the same annualisation logic as the Configure mode tier summary.

---

## The floating changes tray (detailed behaviour)

See Prompt 1 v2 for the tray trigger/badge. Here are the Adjust-mode specific behaviours:

- The tray always shows changes relative to the currently active tier's published version (or template if not yet published)
- When HR switches tiers, the tray count updates to reflect changes for the newly active tier
- A "Show all tiers" toggle in the tray header expands to show changes across all tiers (not just the active one)

---

## What Adjust mode does NOT show

- The Configure mode benefit card (that's a full-screen experience, accessed via mode switch)
- Any employee-facing views (accessible via Preview button in the header)
- The comparison dashboard (separate "Policy vs. Reality" tab)
- The PDF import flow (accessible via "Import from document" in the header)

---

## API connections for this prompt

| Purpose | Endpoint |
|---|---|
| Load draft (all tiers) | `GET /api/hr/policy-config` (no filters — load full payload) |
| Save draft changes | `PUT /api/hr/policy-config/draft` |
| Revert a row | `POST /api/hr/policy-config/draft/revert-row` |
| Get diff vs published | `GET /api/hr/policy-config/diff` |
| Country list (jurisdiction overrides) | `GET /api/suppliers/countries` |
| Published version for revert baseline | `GET /api/hr/policy-config/published` |

---

## Performance constraints

- The full draft payload can contain up to 31 benefits × N tiers. Load all at once on mount (no pagination). Cache in context — don't re-fetch on tab switch.
- Accordion expand/collapse is client-side only — no API call on open/close.
- Amount field edits are debounced 800ms before being written to the draft state. The auto-save then fires every 20 seconds.
- Change indicators are computed client-side by comparing the current draft value to the baseline (template default or published value, stored in context on mount).
