# PROMPT 2a — Configure Mode: One Tier, One Benefit at a Time

## Context

This prompt is part of the ReloPass HR Policy Builder. Prompt 1 (v2) covers the page shell, mode switcher, and template selection. This prompt covers **Configure mode** in full — the guided flow where HR walks through benefits for a single tier, one benefit card at a time.

The core UX contract of Configure mode: **HR sees exactly one thing at a time. One benefit. One decision. Nothing else.**

---

## Tech stack

- React 18 + TypeScript, TailwindCSS
- Design system: `frontend/src/components/antigravity/`
- State lives in `PolicyBuilderContext` (established in Prompt 1 v2). Configure mode reads the draft benefits for the active tier and tracks which benefits have been reviewed.
- No new routing — Configure mode is rendered inside `/hr/policy-builder` as a content-area state.

---

## The Configure mode flow for a single tier

After HR selects a tier from the tier selection screen (Prompt 1 v2), they enter a sequential review flow. The flow has three phases:

**Phase A — Benefit review** (the main loop): Benefits are presented in priority order, one at a time. HR makes one decision per benefit and moves forward.

**Phase B — Tier summary**: After all benefits are reviewed, a summary card shows everything configured for this tier. HR can go back to any benefit.

**Phase C — Return to tier list**: HR returns to the tier selection screen to configure the next tier, or to publish.

---

## Priority order for benefits

Benefits are presented in this order within Configure mode (highest business impact first):

1. Host country housing cap
2. Temporary living accommodation
3. Removal & shipping expenses
4. Relocation allowance (assignee + partner)
5. Relocation allowance (per dependent)
6. Shipment of personal goods
7. Mobility premium
8. Living allowance / COLA
9. Child education support
10. Home leave trips
11. Language training
12. Cultural & intercultural training
13. Pre-assignment visit
14. Tax equalisation
15. Spouse / partner assistance
16. Settling-in services
17. Location / hardship allowance
18. Host country transportation
19. Storage (temporary)
20. Extra holiday days
21. Repatriation allowance (assignee + partner)
22. Repatriation allowance (per dependent)
23. Return shipment & travel
24. Payroll structure
25. Banking setup assistance
26. Tax return preparation
27. Medical exam reimbursement
28. Visa & work permit assistance
29. Dual-career support
30. Driving test reimbursement
31. Custom benefits (if any added)

---

## Progress indicator

At the top of the content area (below the page header breadcrumb), a horizontal progress bar spanning the full width of the content area:

```
Manager  ──────────────────────────────────────  3 of 26 benefits reviewed
         [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]
```

- Tier name on the left
- "N of 26 benefits reviewed" on the right
- Thin progress bar below
- As HR marks each benefit (Keep / Adjust / Exclude), the bar fills

Below the bar, a secondary line in muted text: "Skip any benefit to decide later — you can return to skipped ones at the end."

---

## The benefit card

The benefit card is the centrepiece of Configure mode. It is centred on the page, ~600px wide, with generous vertical padding. Everything else is suppressed — no sidebar, no accordion, no grid visible behind it.

### Card anatomy

```
┌──────────────────────────────────────────────────────────┐
│  RELOCATION ASSISTANCE                                   │  ← category label, small, muted
│                                                          │
│  Relocation allowance                                    │  ← benefit name, large (H2)
│  (assignee + partner)                                    │
│                                                          │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  Template value for Manager:                             │  ← pre-filled value section
│                                                          │
│       €  1,500        / one-time                        │
│       [  amount input, large, editable  ] [freq. sel.]  │
│                                                          │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  ⬡ Market context · Germany                             │  ← inline benchmark (collapsed)
│    Platform median: €1,800 · Range: €800 – €3,000       │
│    Your value covers ~60% of historical cases  ↑        │
│                                                          │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  [ ✓ Keep this value ]  [ ✎ Adjust ]  [ — Exclude ]    │  ← the three decisions
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Section 1 — Category label

Small, uppercase, muted text (e.g. "RELOCATION ASSISTANCE"). Acts as a wayfinding anchor — HR always knows which bucket they're in.

### Section 2 — Benefit name

Large H2 (24px, semi-bold). If the name is long (e.g. "Relocation allowance (assignee + partner)"), wrap it naturally — do not truncate. Below the name, a one-line description in muted text (13px) explaining what this benefit covers: *"A one-time cash payment to cover the costs of moving the assignee and their partner to the host country."*

### Section 3 — Template value for this tier

This is the pre-filled value from the applied template (Essential / Standard / Generous). Display it prominently:

- Label: "Template value for [Tier name]:" in muted text
- The value itself: a large editable number input (the amount) + a compact frequency selector (one-time / monthly / yearly / per trip / per day / per dependent)
- Currency: inherited from the policy-level currency setting (set in the page header). Show the currency symbol beside the input.

**The input is live — HR can change the value directly here**, without needing to click "Adjust" first. If they change the value and then click "Keep this value", the changed value is kept. The three buttons below are about the coverage decision (covered vs excluded), not about editing.

### Section 4 — Inline market context

A collapsed section below the value, expandable with a chevron. Default state: collapsed but visible as a single line.

**Collapsed state (one line):**
```
⬡ Market context · Germany   Platform median: €1,800   [Show more ↓]
```

**Expanded state:**
```
⬡ Market context · Germany
  
  Platform median:  €1,800 one-time
  Market range:     €800 – €3,000 one-time
  Your value:       €1,500 ← (current input value, updates live)
  
  Coverage estimate: Your value covers ~60% of historical selections
  on the ReloPass platform for this benefit in Germany.
  
  [ Set to median (€1,800) ]
```

The "Set to median" button updates the amount input above and stays within the card flow — it doesn't navigate anywhere.

Market context data source:
- Median / range: from historical `policy_config_benefits.amount_value` across same `benefit_key` on the platform
- Coverage estimate: approximated from the spend distribution data (Prompt 4 endpoint: `GET /api/hr/assignments/benefit-spend-summary`)
- Country: defaults to the company's primary destination country (from company profile). HR can change it via a small country selector in this section.

### Section 5 — The three decisions

Three buttons in a row, full-width, clearly separated from the content above:

**[ ✓ Keep this value ]** — Primary style. Marks this benefit as covered at the displayed amount. Advances to the next benefit card.

**[ ✎ Adjust ]** — Secondary style. Expands an **Adjust panel** below the buttons (see below). Does not advance.

**[ — Exclude ]** — Destructive-ghost style. Marks this benefit as not covered for this tier. Shows a brief confirmation inline ("Exclude [Benefit name] for [Tier]?") with `Confirm` and `Cancel` before advancing.

### The Adjust panel (expanded below the three buttons)

When HR clicks Adjust, a panel slides down below the buttons:

```
┌──────────────────────────────────────────────────────────┐
│  Adjust for Manager                                      │
│                                                          │
│  Coverage:  [● Covered]  [○ Excluded]  [○ Optional]     │
│                                                          │
│  Value type:  [● Fixed amount]  [○ % of salary]         │
│                                                          │
│  Amount:  €  [_____]   / [one-time ▼]                   │
│                                                          │
│  Apply a cap?  [ ] Yes                                   │
│  (if checked: Cap at €[___] / [period ▼]. Above cap:    │
│   [HR approval required ▼])                              │
│                                                          │
│  Applies when:  (conditions — optional)                  │
│  [ ] Only if accompanied family                          │
│  [ ] Only if assignment > [12] months                    │
│                                                          │
│  Notes for HR team (internal only):                      │
│  [______________________________________________]        │
│                                                          │
│  [ Save & continue → ]    [ Cancel ]                     │
└──────────────────────────────────────────────────────────┘
```

"Save & continue" saves the benefit configuration and advances to the next card. All fields pre-filled from the template — HR only needs to change what differs.

---

## Navigation between benefits

### Bottom navigation bar

Below the card, a persistent navigation bar:

```
[ ← Previous ]    Benefit 3 of 26    [ Skip for now ]    [ Next → ]
```

- **← Previous**: Go back to the previous benefit (can re-review any benefit already seen)
- **Skip for now**: Marks the benefit as "skipped" (grey dot in progress). HR can return to all skipped benefits at the end.
- **Next →**: Advances to the next benefit. Only enabled after a decision (Keep / Exclude / Adjust+Save) has been made for the current benefit. Exception: Skip also enables Next.

### Keyboard shortcuts

- `Enter` or `K` → Keep this value
- `E` → Exclude (shows confirmation)
- `A` → Open Adjust panel
- `S` → Skip
- `←` / `→` → Previous / Next (when no input is focused)

These are shown as a small hint row below the navigation bar: "Keyboard: K keep · A adjust · E exclude · S skip"

---

## Handling skipped benefits

At the end of the 31 benefits (or when HR clicks "Review skipped" at any point), if there are skipped benefits, show a screen:

```
You skipped 4 benefits for Manager.
Review them now or publish with template defaults.

[ Storage (temporary) ]          Template: €500 one-time  [ Review ] [ Keep default ] [ Exclude ]
[ Driving test reimbursement ]   Template: €200 one-time  [ Review ] [ Keep default ] [ Exclude ]
[ Dual-career support ]          Template: Excluded        [ Review ] [ Keep default ]
[ Payroll structure ]            Template: Text note       [ Review ] [ Keep default ] [ Exclude ]
```

HR can deal with each skipped item inline on this screen without re-entering the card-by-card flow.

---

## Tier summary screen (Phase B)

After all benefits are reviewed (no more skipped), show the Tier Summary screen:

### Layout

A two-column layout inside the ~600px centred card area.

**Left column — Coverage summary:**
```
Manager tier — 26 benefits configured

  ✓ Covered (19)     → [list as compact chips]
  — Excluded (5)     → [list as compact chips]
  ✱ Optional (2)     → [list as compact chips]
```

**Right column — Budget estimate:**
```
Estimated annual cost

  One-time costs:      €12,400
  Monthly recurring:   €3,200 /mo  (€38,400/yr)
  ─────────────────────────────
  Total annual est.:   €50,800

  ⚡ 3 changes from Standard template
     [View changes]
```

The budget estimate is calculated client-side by summing all covered, currency-type benefits (annualising monthly/yearly figures).

Below the summary: two CTAs:

```
[ ← Edit any benefit ]    [ Configure next tier → ]
```

"Configure next tier" returns to the tier selection screen (Prompt 1 v2) and marks this tier as complete (green dot).

---

## API connections for this prompt

| Purpose | Endpoint |
|---|---|
| Read draft benefits for a tier | `GET /api/hr/policy-config?employeeLevel={level}&assignmentType={type}&familyStatus={status}` |
| Save benefit decision | `PUT /api/hr/policy-config/draft` (full draft payload, debounced) |
| Market context / spend data | `GET /api/hr/assignments/benefit-spend-summary?benefit_key={key}&destination_country={code}` |
| Revert a benefit to template | `POST /api/hr/policy-config/draft/revert-row` |

---

## What Configure mode does NOT show

To maintain focus, Configure mode explicitly hides:

- The full benefit grid (that's Adjust mode)
- The provider context sidebar (market context is inline in the card)
- The comparison dashboard (separate tab)
- Jurisdiction overrides (available in Adjust mode's Advanced expand)
- The policy diff panel (accessible via the floating changes tray from Prompt 1 v2)

HR can switch to Adjust mode at any time via the mode pill in the header — they don't lose any progress.
