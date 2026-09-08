# PROMPT 5 — Policy vs. Reality: Comparison Dashboard

## Context

This prompt is part of the ReloPass HR Policy Builder feature. This is the second top-level tab in the Policy section of the HR portal, sitting alongside the Policy Builder tab (Prompts 1–4). While the Policy Builder is where HR *creates* policy, this tab is where HR *understands what's actually happening* — comparing what the company promised versus what employees selected from service providers.

This is a **strategic overview dashboard** with two layers:
1. **Aggregate view**: All active relocations at once — are employees staying within policy?
2. **Per-employee drill-down**: Click any employee case to see a detailed side-by-side of their policy entitlement vs. their actual selections.

The design should be fresh — don't mirror the existing `HrRfqQuotesPolicyCapsSection`. That existing component covers a narrow caps-vs-RFQ view per assignment. This tab replaces and supersedes it at the company level.

---

## Tech stack & design system

- **Framework**: React 18 + TypeScript, Vite, TailwindCSS
- **Design system**: `frontend/src/components/antigravity/` — DataTable, Card, Badge, Alert, Tabs, Select, Tooltip, Drawer.
- **Route**: `/hr/policy-vs-reality`
- **Data fetching**: Axios wrappers in `frontend/src/api/`. New endpoints should be designed as part of this prompt.
- **Chart library**: Use `recharts` (already in the frontend bundle) for all visualisations.

---

## Page header

- **Title**: "Policy vs. Reality"
- **Subtitle**: "Compare your company's policy commitments against what employees are actually selecting."
- **Top-right controls**:
  - `Period` filter: Last 3 months | Last 12 months | All time | Custom range
  - `Destination` filter: All countries | specific country dropdown (from `GET /api/suppliers/countries`)
  - `Tier` filter: All tiers | specific tier name
  - `Assignment type` filter: All | long_term | short_term | permanent | etc.
  - `Export` button: Download current view as CSV

---

## Section 1 — KPI summary bar

Four metric cards in a horizontal row at the top:

### Card 1: Policy compliance rate
"83% of benefits selections are within policy caps"
- A large percentage number
- A small trend arrow vs. previous period: "↑ 4% vs last quarter"
- Color: green if ≥ 80%, amber if 60–79%, red if < 60%

### Card 2: Total active relocations
"14 active assignments"
- Count of currently active cases
- Subtitle: "X on long-term · Y on short-term · Z permanent"

### Card 3: Average overage per assignment
"€1,240 average overage"
- Mean overage amount (sum of all over-cap selections / number of assignments with at least one overage)
- Shown in the policy default currency
- "No overages" state if zero

### Card 4: Most exceeded benefit
"Host housing cap — exceeded in 6 of 14 cases"
- The benefit key most frequently over-cap
- Click navigates to the category drill-down (Section 3)

---

## Section 2 — Aggregate compliance heatmap

A matrix table where:
- **Rows** = the 31 canonical benefit keys (grouped by the 6 categories, same as Prompt 2)
- **Columns** = active assignment cases (anonymised as "Case #1", "Case #2", etc. in the aggregate view — real names shown in the per-employee drill-down)

### Cell coloring (traffic light):
- **Green** `✓`: Employee selected within policy cap
- **Amber** `~`: Employee selected within 10% above cap (soft overage — may be HR-approved)
- **Red** `!`: Employee selected more than 10% above cap (hard overage)
- **Grey** `—`: Benefit not selected / not applicable to this case
- **Blue** `○`: Benefit covered by policy but employee hasn't made a selection yet (pending)

### Cell content on hover:
Show a tooltip:
```
[Employee tier] · [Destination]
Policy cap: €2,500/mo
Employee selected: €3,200/mo (Supplier: [Name])
Overage: €700/mo (+28%)
Status: Pending HR approval
```

### Row-level summary (rightmost column):
- "6/14 exceeded" with a mini bar visualising the proportion
- Colour of the count badge matches the most severe status in that row

### Column-level summary (bottom row):
- Per-case: "3 overages · 1 pending" in compact text
- Overall compliance score for that case (e.g. "73%") as a small circular badge

### Table controls:
- Toggle: `Show all benefits` | `Show overages only` (filters rows to only those with at least one amber/red cell)
- Sort columns by: Case start date | Compliance score | Tier
- Sticky first column (benefit names) and sticky header row (case IDs)

---

## Section 3 — Category breakdown charts

Below the heatmap, a row of **6 small bar charts** — one per benefit category. Each chart shows:
- X-axis: benefit keys within that category
- Y-axis: average overage % across all cases (can be negative = under budget)
- Bar color: green (within cap), amber (soft overage), red (hard overage)
- Hover: shows exact average + number of cases

Clicking any bar highlights that benefit row in the heatmap above (scroll to it) and opens the per-benefit drill-down drawer (Section 5).

---

## Section 4 — Per-employee case list

Below the charts, a **data table** listing each active assignment:

| Column | Description |
|---|---|
| Case ref | Anonymised ID in aggregate; real name in full access mode |
| Destination | Country flag + city |
| Tier | Tier name badge |
| Assignment type | Badge (long-term, short-term, etc.) |
| Compliance score | % of benefits within cap, shown as a colored bar |
| Overages | Count of over-cap benefits (red badge if > 0) |
| Total policy budget | Sum of all covered benefits for their tier |
| Total actual spend | Sum of all employee selections (confirmed + pending) |
| Variance | Actual − Policy. Red if positive, green if negative. |
| Status | Active / Completed / Pending selections |
| Actions | `View details →` |

The table is sortable by all columns. Pagination: 15 rows per page. Clicking any row OR "View details →" opens the **Per-case Detail Drawer** (Section 5).

---

## Section 5 — Per-case Detail Drawer

A right-side drawer (~600px wide, full height) showing one employee's full policy entitlement vs. their actual selections.

### Drawer header:
- Case reference / employee name (with privacy toggle)
- Destination: "Paris, France 🇫🇷"
- Assignment type + duration
- Tier: "[Tier name]" badge
- Compliance score: large number "74%" with color
- Start date / end date

### Drawer body: Side-by-side benefit table

For each benefit the employee is entitled to:

```
[ Benefit name ]

Policy says:                    Employee selected:
€2,500/month (host housing)     €3,200/month — Nestpick Paris
                                ⚠ €700/month over cap (+28%)
                                [ Approve overage ]  [ Flag for review ]
```

Status per benefit:
- Within cap → green checkmark, no action needed
- Soft overage → amber warning, `Approve overage` button
- Hard overage → red alert, `Flag for review` button + optional notes field
- Not yet selected → grey, "Awaiting employee selection" with a countdown if there's a deadline
- Not applicable → shown in a collapsed "Not applicable" section at the bottom

### Overage approval flow:
Clicking `Approve overage` on a benefit row shows an inline confirmation:
- "Approve €700/month overage for host housing?"
- A notes field: "Reason (optional)"
- `Confirm approval` button → calls `POST /api/hr/assignments/{case_id}/benefit-overages/{benefit_key}/approve`
- Once approved, the row shows: "✓ Approved by you on [date]" and the heatmap cell turns from red to amber.

### Drawer footer:
- `Download case report` (PDF): Generates a per-case compliance report
- `Email summary to employee` ghost button
- Navigation: `← Previous case` | `Next case →` (allows HR to step through cases without closing/reopening the drawer)

---

## Policy calibration panel (strategic view)

At the very bottom of the page, a collapsible section titled **"Policy calibration"** — for strategic review, not operational tracking.

### Purpose:
Help HR understand whether their policy is set correctly for the market. Not "is this employee over budget?" but "is our budget realistic for where we send people?"

### Layout: Two charts side by side

**Chart A — Cap adequacy by benefit**
For each benefit with a cap configured:
- How often the cap is exceeded across all historical assignments (bar chart, sorted by exceedance rate descending)
- Benchmark line: platform average exceedance rate across all ReloPass companies
- If your cap is exceeded more often than the benchmark: "Consider raising this cap" tooltip

**Chart B — Spend vs. cap over time**
A line chart (recharts `LineChart`) with time on X axis and two lines:
- `Policy cap` (flat or stepped line, changes when policy is republished)
- `Average actual spend` (rolling average of what employees spent per period)
- When the two lines diverge significantly, show a shaded "gap" area

Below Chart B, a recommendation text block generated from the analysis:
> "Your housing cap in Germany (€2,500/mo) covers only 58% of actual selections over the last 12 months. The market has moved — consider revising to €2,900/mo to align with current provider pricing."

A `Update policy` button below the recommendation opens the Policy Builder tab pre-scrolled to the affected benefit row.

---

## API connections for this prompt

All new endpoints to design:

| Purpose | Endpoint |
|---|---|
| Aggregate compliance data | `GET /api/hr/policy-compliance/summary?period=&destination=&tier=&assignment_type=` |
| Heatmap matrix data | `GET /api/hr/policy-compliance/matrix?period=&destination=&tier=` |
| Per-case list | `GET /api/hr/policy-compliance/cases?period=&destination=&tier=&page=&limit=` |
| Per-case detail | `GET /api/hr/policy-compliance/cases/{case_id}` |
| Approve overage | `POST /api/hr/assignments/{case_id}/benefit-overages/{benefit_key}/approve` |
| Historical spend trend | `GET /api/hr/policy-compliance/spend-trend?benefit_key=&destination=&period=` |
| Policy calibration analysis | `GET /api/hr/policy-compliance/calibration?destination=` |
| Export CSV | `GET /api/hr/policy-compliance/export?format=csv&period=&destination=&tier=` |

These endpoints aggregate data from:
- `policy_config_benefits` — what the policy says
- Assignment case data — what employees selected (RFQ quotes, confirmed bookings)
- Supplier data — provider names and pricing

---

## UX constraints

- The heatmap table can have many rows (31 benefits) and many columns (active cases). Implement virtual scrolling for columns if more than 10 cases are active simultaneously.
- All employee-identifying data must be toggleable: a "Privacy mode" switch in the header that anonymises names → "Case #7" format. Default to showing real names (HR has access), but allow the toggle for when HR is sharing their screen.
- The page must degrade gracefully with < 3 active assignments: show the case list and drawer, but replace charts with "Not enough data for charts — you need at least 3 active assignments for statistical views."
- All recharts visualisations must include a data table fallback for accessibility (`<table>` with `aria-hidden` on the SVG, `aria-label` on the fallback).
- The `Export` button is critical for HR workflows — ensure it exports exactly what's visible on screen (respecting active filters), not all data.
