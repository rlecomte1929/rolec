# PROMPT 4 — HR Policy Builder: Live Provider Context Sidebar

## Context

This prompt is part of the ReloPass HR Policy Builder feature. Prompts 1 & 2 cover the canvas builder; Prompt 3 covers PDF import. This prompt covers the **contextual intelligence sidebar** — a collapsible panel that HR can open while configuring any benefit to see real market data: what providers charge, which suppliers are active in a given destination, and what past employees have actually selected and spent.

The goal is to help HR set amounts that are grounded in reality — not guesses. The sidebar turns the policy canvas from a blank form into an informed decision surface.

---

## Tech stack & design system

- **Framework**: React 18 + TypeScript, Vite, TailwindCSS
- **Design system**: `frontend/src/components/antigravity/` — Tabs, Card, Badge, Tooltip, Skeleton, Alert.
- **Position**: Fixed right panel, ~360px wide, slides in from the right edge of the screen. The canvas shifts left to make room (don't overlap). On screens < 1440px, the sidebar overlaps the canvas instead of pushing it.
- **State**: Context-aware — the sidebar responds to which benefit row the HR user is currently hovering or editing. It updates its content automatically based on the active benefit key.

---

## Sidebar trigger

The sidebar is toggled via a `Context` button in the Policy Builder page header (Prompt 1), with a chart/insights icon. When active, the button shows a filled icon + "Context on" label.

Additionally, when HR opens the **Benefit Detail Drawer** (Prompt 2), show a smaller inline "Market data" section at the bottom of the drawer that mirrors the sidebar content for that specific benefit. This gives HR the data without having to open the full sidebar separately.

---

## Sidebar header

- Title: "Market context"
- Subtitle: Dynamic — shows the currently focused benefit name. Example: "Host country housing cap" or "All benefits" if no specific benefit is focused.
- A **destination country selector**: A searchable dropdown (calls `GET /api/suppliers/countries`) defaulting to the company's primary destination country (from company profile). Changing the country updates all three panels below.
- A small `?` tooltip explaining: "Data is based on ReloPass supplier network, historical assignments on this platform, and publicly available mobility benchmarks."

---

## Three tabs inside the sidebar

### Tab 1 — Market benchmarks

**Purpose**: Show HR the typical market cost for the focused benefit in the selected destination country.

**Source**: This data comes from two places:
1. `GET /api/suppliers/search?service_category={category}&destination_country={code}` — real supplier pricing ranges from the SupplierServiceCapability model (`min_budget`, `max_budget`)
2. Historical facts extracted from policy documents — average of `amount_value` across canonical policy facts for the same `benefit_key`

**Layout**:

A horizontal bar chart or range visualisation per benefit (or just the focused one if a specific benefit is selected):

```
Host country housing cap — Germany

  Market range:     [████████████░░░░░░░░] €1,200 – €3,800/mo
  Platform average: [████████████████░░░░] €2,100/mo  ← dashed line
  Your current cap: [██████████████░░░░░░] €2,500/mo  ← colored line
```

Show three reference points:
- **Market range** (grey bar): min_budget to max_budget from active suppliers in that country
- **Platform average** (dashed line): mean amount across policies on ReloPass for that benefit + destination
- **Your current cap** (colored line): the value HR currently has configured in the canvas for the active tier (or "Not set" if unconfigured)

Below the chart, a short contextual note generated from the data. Examples:
- "Your cap is above the market median — generous relative to the network."
- "Your cap is below the market floor — employees may struggle to find suitable housing within this budget."
- "No supplier data available for this destination. Showing platform averages only."

If multiple tiers are configured, show a small multi-line view with each tier's value on the same chart for comparison.

**Benefit category mapping to service categories** (how benefit_key maps to supplier service_category for the API call):
| benefit_key | service_category query |
|---|---|
| `host_housing_cap` | `housing` |
| `child_education_support` | `school_search` |
| `removal_expenses`, `shipment_of_goods` | `movers` |
| `temporary_living` | `temporary_housing` |
| `settling_in_services` | `settling_in` |
| `banking_assistance` | `banking` |
| `language_training` | `language_school` |
| `cultural_training` | `cultural_coaching` |
| Others | show platform average only |

---

### Tab 2 — Active providers

**Purpose**: Show which suppliers are actually available and active in the selected destination country for the currently focused benefit category.

**Source**: `GET /api/suppliers/search?service_category={category}&destination_country={code}&status=active`

**Layout**: A list of provider cards. Each card shows:
- Provider name + verified badge (if `verified: true`)
- Rating: star display based on `average_rating`, review count in parentheses
- Budget range: `€X – €Y` from the capability record
- Tags: up to 3 `specialization_tags` shown as small badges
- Preferred partner badge if `preferred_partner: true`
- `View profile →` link (navigates to admin supplier detail, opens in new tab)

If no providers found: "No active providers found for [category] in [country]. Consider expanding coverage or adjusting your policy to reflect what's available."

Show a count badge on the Tab 2 label: "Active providers (7)" — populated after the API call.

**Why this matters for policy creation**: If only 2 providers serve a country in a category, and their minimum price is €2,000/month, setting a cap below that means employees have no compliant options. The sidebar makes this visible at policy-creation time, not after an employee is stuck.

---

### Tab 3 — Historical selections

**Purpose**: Show what past employees at this company (and anonymised across the platform) actually selected and spent — the ground truth that validates whether the policy was realistic.

**Source**: Two queries to existing assignment data:
- Company-specific: `GET /api/hr/assignments/benefit-spend-summary?benefit_key={key}&destination_country={code}` — (design this endpoint; it should aggregate actual spend from completed assignments)
- Platform-wide (anonymised): same endpoint with a `platform_wide=true` flag

**Layout**: A compact analytics view with three sub-sections:

**Sub-section A — Selection rate**
"Of 12 employees who had this benefit available in Germany, 9 (75%) used it."
Show as a donut or horizontal usage bar.

**Sub-section B — Actual spend distribution**
A box plot or simplified range: min / median / max of what employees actually spent.
```
Actual spend — Host housing — Germany
  Min:    €1,400/mo
  Median: €2,200/mo  ← 50% of employees
  Max:    €3,600/mo
  Your cap: €2,500/mo  (covers 68% of cases)
```
The "Your cap covers X% of cases" line is the most valuable insight — compute it by comparing the current cap to the spend distribution.

**Sub-section C — What employees selected** (company-specific only)
A compact list of the last 5 completed assignments that used this benefit (anonymised: "Employee A — Berlin — Long-term — Selected: €2,100/mo" without name). Clicking "View all" opens the comparison dashboard tab (Prompt 5).

If company has fewer than 3 completed assignments for this benefit: "Not enough company data yet — showing platform-wide averages."

---

## Sidebar footer

A persistent footer at the bottom of the sidebar (below all tabs):

- **"Apply median to canvas"** button: Sets the current tier's amount for the focused benefit to the platform median for the selected country. Confirmation tooltip: "This will set [Benefit] to €X,XXX in [Tier]."
- **"Apply to all tiers"** variant: A dropdown on the button that offers "Apply to all tiers" as an alternative.
- A small disclaimer: "Benchmarks are indicative and sourced from the ReloPass network. Not legal or tax advice."

---

## Empty / loading states

- While data loads, show Skeleton placeholders matching the layout of each tab panel.
- When no benefit is focused (HR hasn't hovered/selected a cell yet): show a "Select a benefit to see context" state with a simple illustration.
- When a benefit has no market data at all: "No benchmark data available for this benefit yet. Contact ReloPass to request data coverage for this category."

---

## API connections for this prompt

| Purpose | Endpoint |
|---|---|
| Destination country list | `GET /api/suppliers/countries` |
| Supplier search by category + country | `GET /api/suppliers/search?service_category={cat}&destination_country={code}&status=active` |
| Company benefit spend summary | `GET /api/hr/assignments/benefit-spend-summary?benefit_key={key}&destination_country={code}` |
| Platform-wide spend (anonymised) | `GET /api/hr/assignments/benefit-spend-summary?benefit_key={key}&destination_country={code}&platform_wide=true` |

Note: The `benefit-spend-summary` endpoint is new — design it to return: `{ benefit_key, destination_country, sample_count, usage_rate, spend_min, spend_median, spend_max, spend_p25, spend_p75, recent_cases: [{ case_ref, destination_city, assignment_type, spend_value }] }`.

---

## UX constraints

- The sidebar must not block critical canvas interactions. If the screen is too narrow, collapse it to an icon-bar mode (tabs become icon buttons, content loads in a tooltip/popover on hover).
- Data refreshes automatically when the destination country selector changes. No manual refresh needed.
- The "Your current cap" reference line updates in real-time as HR types in the canvas — no save required to see the comparison.
- All currency amounts in the sidebar use the same currency as the policy default (set in the canvas header).
