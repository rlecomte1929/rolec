# PROMPT 1 — HR Policy Builder: Page Shell & Tier Canvas

## What you are building

A new page inside the ReloPass HR portal called **Policy Builder**. This replaces the current flat filter-based policy config page with a visual **canvas model** where tiers are the primary axis. The target user is an HR Mobility lead — someone responsible for setting up their company's relocation policy, not a developer or platform admin.

This prompt covers: the full page layout, the top navigation/header, the tier column canvas, and the tier creation/naming/rule-assignment flow. Benefit configuration within each tier is covered in Prompt 2.

---

## Tech stack & design system

- **Framework**: React 18 + TypeScript, Vite, TailwindCSS
- **Design system**: `frontend/src/components/antigravity/` — use components from this system first (Button, Card, Input, Badge, Alert, Dropdown, Drawer, Modal, Tabs, Tooltip). Do not introduce external UI libraries.
- **Routing**: React Router 6. This page lives at `/hr/policy-builder`.
- **Data fetching**: Axios wrappers in `frontend/src/api/`. No direct fetch calls in components.
- **State**: No global store. Use local component state + React context scoped to this feature.
- **Styling**: Tailwind utility classes only. Responsive down to 1280px width minimum (HR portal is desktop-first).

---

## Page structure

The page has **two top-level tabs** in the HR portal navigation area:

1. **Policy Builder** (this prompt — the creation surface)
2. **Policy vs. Reality** (Prompt 5 — the comparison dashboard)

Both tabs live under the HR portal sidebar, nested under "Policy" in the nav. The active tab is indicated by an underline/pill style consistent with the rest of the HR portal.

### Page header (inside Policy Builder tab)

Sticky header, ~64px tall, containing:

- **Left**: Page title "Policy Builder" in H2, below it a one-line status badge showing the current policy state. States are: `draft` (amber), `published` (green), `no policy` (grey). Next to the badge show the version label if one exists (e.g. "v2.1 · Effective 1 Jun 2026").
- **Center**: A segmented control or breadcrumb showing the two main modes: `Build from template` | `Import from document`. This is the primary mode switcher for the entire canvas — toggling between modes does not clear the canvas but changes the right-side context panel (see Prompt 3 for import mode).
- **Right**: Three action buttons — `Save draft` (secondary style), `Preview employee view` (ghost), `Publish` (primary, disabled until all tiers are valid). Add a version history icon button (clock icon) that opens a side drawer listing prior versions.

---

## The Tier Canvas

The main body of the page below the header is the **tier canvas**. This is the core innovation of the page.

### Layout: Columns = Tiers

```
[ Sidebar: Benefit Categories ] [ Tier 1 ] [ Tier 2 ] [ Tier 3 ] [ + Add tier ]
```

- The **left sidebar** (~240px fixed) lists the 6 benefit categories as sticky section headers with expand/collapse. Categories are not interactive here — they are anchors. See Prompt 2 for the row-level benefit content.
- Each **tier column** is ~320px wide, horizontally scrollable if there are more than 3–4 tiers on screen.
- The **+ Add tier** button appears as a dashed column placeholder at the right end of the canvas.

### Tier column header (per column)

Each tier column has a header card (~120px tall) above the benefit rows. It contains:

- **Tier name** (editable inline — click to edit, shows an input field). Default names map to: `Entry`, `Manager`, `Director`, `VP`, `C-Suite`. Custom names are allowed.
- **Employee count badge**: A small grey badge showing how many active employees are currently assigned to this tier (pulled from `GET /api/hr/assignments/count?tier=<tier_key>` — mock this endpoint reference). If 0, show "0 employees" in muted text.
- **Tier color swatch**: A small colored dot/stripe that color-codes the tier throughout the canvas. Auto-assign from a palette of 5 accessible colors (one per tier). Allow HR to click the swatch to change it.
- **Targeting rules summary**: Below the tier name, show a compact summary of the rules that assign employees to this tier. Example: `"Manager · Accompanied · Long-term"`. This is a collapsed view — clicking it opens the **Tier Rules Drawer** (see below).
- **Three-dot menu** on hover: options are `Duplicate tier`, `Reorder left/right`, `Delete tier` (with confirmation if employees are assigned).

### Budget model toggle (per tier header)

Directly below the targeting summary in each tier header, show a small toggle:

- **Lump sum** mode: The tier gives employees a single total budget they allocate themselves. Show a currency input field for the total amount.
- **Per-category caps** mode: Each benefit row in the column gets its own cap. The total is the sum of all covered benefits.

The toggle is a 2-option segmented control: `Lump sum` | `Category caps`. When switching from per-category to lump sum, show a confirmation toast: "Switching to lump sum will hide individual caps. Individual settings are preserved if you switch back."

If lump sum is selected, the benefit rows in this column collapse to show only inclusion/exclusion toggles (not amounts). Show a summary bar at the bottom of the column: "Total: €12,400 / year" (the inputted lump sum).

---

## Tier Rules Drawer

When HR clicks the targeting summary in a tier header, a right-side drawer opens (~480px wide, full height). This is where HR defines who belongs to this tier using **three rule axes**:

### Axis 1: Employee level
Multi-select checkboxes. Options map to canonical values from the backend:
- `entry` → "Entry level / Graduate"
- `manager` → "Manager / Senior IC"
- `director` → "Director"
- `vp` → "VP / Head of"
- `c_suite` → "C-Suite / Executive"

### Axis 2: Assignment type
Multi-select checkboxes. Options:
- `long_term` → "Long-term assignment (>12 months)"
- `short_term` → "Short-term assignment (3–12 months)"
- `permanent` → "Permanent transfer"
- `commuter` → "Cross-border commuter"
- `extended_business_trip` → "Extended business trip (<3 months)"

### Axis 3: Family status
Multi-select checkboxes. Options:
- `single` → "Single / No dependents"
- `married` → "Married / Partner (no dependents)"
- `accompanied_family` → "With accompanying dependents"

### Conflict detection
After the HR sets rules, check for overlap with other tiers. If Employee level "Manager" + Assignment type "long_term" is already claimed by another tier, show an inline warning banner in the drawer: "⚠️ Overlap detected with [Tier Name]. An employee matching these conditions would be assigned to the first matching tier. Drag to reorder tiers to set priority."

### Tier ordering & priority
Below the canvas columns, add a small note: "Tiers are evaluated left to right. The first matching tier wins." Add a `Reorder tiers` button that enables drag-to-reorder mode on the columns.

---

## Empty state

When no tiers exist (first-time setup):

Show a centred empty state in the canvas area with:
- Illustration placeholder (use a simple SVG of layered cards/columns)
- Title: "No tiers configured yet"
- Subtitle: "Start from a template to get set up in minutes, or build your own tier structure from scratch."
- Two CTAs: `Start from a template` (primary) | `Add a tier` (secondary)

Clicking "Start from a template" calls `GET /api/hr/policy-config/templates` and shows a modal with the available template cards (key, label, description). Selecting one calls `POST /api/hr/policy-config/draft/apply-template` and populates the canvas with pre-built tiers.

---

## API connections for this prompt

| Purpose | Endpoint |
|---|---|
| Load working payload (draft or published) | `GET /api/hr/policy-config?assignmentType=&familyStatus=&employeeLevel=` |
| Ensure draft exists | `POST /api/hr/policy-config/draft` |
| Save draft changes | `PUT /api/hr/policy-config/draft` |
| List templates | `GET /api/hr/policy-config/templates` |
| Apply template | `POST /api/hr/policy-config/draft/apply-template` |
| Version history | `GET /api/hr/policy-config/history` |
| Publish policy | `POST /api/hr/policy-config/publish` (requires `effective_date`, `policy_version`) |

The `PUT /api/hr/policy-config/draft` payload shape uses `policy_config_benefits` rows with fields: `benefit_key`, `benefit_label`, `category`, `covered` (bool), `value_type` (currency|percentage|text|none), `amount_value`, `currency_code`, `unit_frequency`, `cap_rule_json`, `assignment_types` (jsonb array), `family_statuses` (jsonb array), `employee_levels` (jsonb array).

---

## Key UX constraints

- Auto-save draft every 30 seconds while the HR has unsaved changes. Show a subtle "Saving…" / "Saved" indicator near the header.
- The canvas must be horizontally scrollable without losing the left benefit-category sidebar (which stays sticky).
- Tier column headers must stay sticky at the top when vertically scrolling through many benefit rows.
- All monetary inputs must support currency selection (EUR, USD, GBP, CHF as defaults). Currency is set at the policy level (header), not per-benefit — individual benefits inherit it unless overridden.
- All interactions must be keyboard-accessible. Tier name inline edit should confirm on Enter, cancel on Escape.
