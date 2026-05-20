# PROMPT 2 — HR Policy Builder: Benefit Matrix Configuration

## Context

This prompt is part of the ReloPass HR Policy Builder feature. Prompt 1 covers the page shell and tier column architecture. This prompt covers everything **inside** the benefit rows of the canvas — how HR configures each of the 31 canonical benefit keys across their tier columns.

The canvas layout is: left sidebar lists benefit categories → each tier is a column → each benefit is a row → the intersection (cell) is where HR configures coverage + amount for that tier.

---

## The 31 canonical benefit keys

Benefits are grouped into 6 categories. These are fixed — HR cannot add or remove categories, but they can add custom benefit rows within a category (stored as custom `benefit_key` values).

### Category 1: Pre-assignment support
| Key | Display label |
|---|---|
| `visa_work_permit_assistance` | Visa & work permit assistance |
| `medical_exam_reimbursement` | Medical exam reimbursement |
| `pre_assignment_visit` | Pre-assignment visit |
| `cultural_training` | Cultural & intercultural training |
| `language_training` | Language training |

### Category 2: Relocation assistance
| Key | Display label |
|---|---|
| `relocation_allowance_assignee_partner` | Relocation allowance (assignee + partner) |
| `relocation_allowance_dependent` | Relocation allowance (per dependent) |
| `removal_expenses` | Removal & shipping expenses |
| `shipment_of_goods` | Shipment of personal goods |
| `storage` | Storage (temporary) |
| `temporary_living` | Temporary living accommodation |
| `settling_in_services` | Settling-in services |

### Category 3: Compensation & allowances
| Key | Display label |
|---|---|
| `mobility_premium` | Mobility premium |
| `location_allowance` | Location / hardship allowance |
| `living_allowance` | Cost-of-living allowance |
| `cola` | COLA (Cost of living adjustment) |
| `host_housing_cap` | Host country housing cap |
| `host_transportation` | Host country transportation |
| `driving_test_reimbursement` | Driving test reimbursement |
| `dual_career_support` | Dual-career support |

### Category 4: Family support & education
| Key | Display label |
|---|---|
| `spouse_partner_assistance` | Spouse / partner assistance |
| `child_education_support` | Child education support |

### Category 5: Leave & repatriation
| Key | Display label |
|---|---|
| `home_leave_trips` | Home leave trips |
| `extra_holiday_days` | Extra holiday days |
| `repatriation_allowance_assignee_partner` | Repatriation allowance (assignee + partner) |
| `repatriation_allowance_dependent` | Repatriation allowance (per dependent) |
| `return_shipment_travel` | Return shipment & travel |

### Category 6: Tax & payroll
| Key | Display label |
|---|---|
| `tax_equalisation` | Tax equalisation |
| `payroll_structure` | Payroll structure |
| `banking_assistance` | Banking setup assistance |
| `tax_return_preparation` | Tax return preparation |

---

## Benefit row anatomy (left sidebar)

Each benefit in the left sidebar column shows:

- **Benefit name** (display label from table above) in regular weight
- **Info icon** (ⓘ): on hover, shows a tooltip explaining what this benefit typically covers (hardcoded descriptions per key)
- **Category color stripe**: a 3px left border in the category's accent color (each of the 6 categories gets a distinct color)
- **+ Add custom benefit** link at the bottom of each category section — opens a small inline form: benefit name + optional description. Custom benefits are stored with a generated key prefixed `custom_`.

Category sections in the sidebar are **collapsible** with a chevron. Collapsed state hides all rows for that category (and collapses the corresponding cells in all tier columns).

---

## Benefit cell (tier × benefit intersection)

Each cell represents the policy configuration for one benefit in one tier. The cell has two states:

### State A — Per-category caps mode (default)

The cell shows a **compact configuration row** with:

1. **Coverage toggle** (leftmost): A checkbox or pill toggle. `Covered` (green) | `Not covered` (red/grey). If not covered, the rest of the cell is greyed out.

2. **Value type selector**: A small dropdown. Options:
   - `currency` → show a numeric input + currency (inherited from policy default)
   - `percentage` → show a % input (of salary or a base amount, configurable)
   - `text` → show a short text input (for "as per host country norms" type values)
   - `none` → no amount needed (e.g. for administrative support benefits)

3. **Amount input**: Visible only when `value_type` is `currency` or `percentage`. For currency: a number input with 2-decimal precision. For percentage: a number input with a % suffix.

4. **Frequency selector**: A compact dropdown. Options: `one-time`, `monthly`, `yearly`, `per trip`, `per day`, `per dependent`, `custom`. Shown only when `value_type` is `currency`.

5. **Cap rule indicator** (optional): A small badge `CAP` in amber if a cap rule exists. On hover, show the cap details. Clicking opens the Cap Rule drawer (see below).

6. **Conditions badge** (optional): A small badge `IF` in blue if conditions are attached. Hovering shows the conditions. Example: "Only if family_status = accompanied_family".

### State B — Lump sum mode

When the tier is in lump sum mode (set in the tier header, Prompt 1), the benefit cells collapse to a simpler view:

- **Coverage toggle only**: `Included` | `Excluded` | `Optional` (employee may choose to use it from their lump sum)
- No amount input (the total budget lives in the tier header)
- The row height is reduced (~32px vs ~56px in per-category mode)

### Cell hover state

On hover over any cell, show a subtle highlight and a `Edit` icon button on the right edge. Clicking opens the **Benefit Detail Drawer** (full configuration for that cell, with all advanced options).

---

## Benefit Detail Drawer

A right-side drawer (~520px wide) for advanced configuration of a single benefit × tier combination. Opens when clicking a cell's Edit button, or double-clicking anywhere on the cell.

### Drawer sections:

**Section 1 — Coverage & value** (same controls as the cell inline view, but with more space and labels)

**Section 2 — Conditions**
Add conditions that restrict when this benefit applies within the tier. Conditions use the same axes as tier targeting:
- Assignment type (multi-select)
- Family status (multi-select)
- Employee level (multi-select within tier)
- Duration threshold (e.g. "Only if assignment > 12 months") — stored as `condition_type: duration_threshold`

Each condition is shown as a tag. "Add condition" button opens a mini form.

**Section 3 — Cap rule**
Define a cap rule for this benefit:
- Cap type: `absolute` (fixed ceiling), `percentage of salary` (e.g. max 20% of base salary), `per unit` (e.g. per dependent, per month)
- Cap value + currency
- Cap period: once per assignment | annual | monthly
- Exceeds cap behavior: `HR approval required` | `Auto-reject` | `Employee covers difference`

**Section 4 — Jurisdiction overrides**
Allow HR to define different amounts or caps for specific destination countries. This is "Section C" of the existing policy system.
- "+ Add country override" button
- Each override: country (searchable dropdown from `GET /api/suppliers/countries`) → value type + amount + currency
- Overrides are listed as compact rows: "🇩🇪 Germany: €2,500 one-time (overrides base €1,800)"

**Section 5 — Notes**
Free-text field for internal HR notes about this benefit (not visible to employees). Stored in `notes` field of `policy_config_benefits`.

**Section 6 — Source trace** (read-only, shown only if policy was imported from a document)
"This rule was extracted from [filename], page 4, clause 3.2. Confidence: 94%." Link to the original chunk. This surfaces the `policy_source_links` data.

---

## Category-level summary footer (per tier column)

At the bottom of each category section within a tier column, show a **subtotal row**:
- If per-category caps mode: "Category subtotal: €X,XXX / year" (sum of covered, currency-type benefits annualized)
- If lump sum mode: "X of Y benefits included"

At the very bottom of each tier column (after all categories), show a **tier total card**:
- Per-category mode: "Estimated annual cost: €XX,XXX" with a breakdown icon
- Lump sum mode: "Lump sum budget: €XX,XXX"
- A small sparkline or color bar showing how this tier compares to others (e.g. "35% of C-Suite tier")

---

## Diff / change indicator

When HR has made changes to a cell that differ from the published version, show a small amber dot on the cell. The cell background gets a very subtle amber tint.

At the top of each tier column, show a banner when changes exist: "X changes from published — [Review diff] [Revert all]"

Clicking "Review diff" triggers `GET /api/hr/policy-config/diff` and shows a side panel listing: added rows, removed rows, changed rows (old value → new value).

Per-row revert uses `POST /api/hr/policy-config/draft/revert-row` with `{ benefit_key, targeting_signature }`.

---

## Validation

Before allowing publish, validate:
- At least one tier exists with at least one covered benefit
- No two tiers have identical targeting rules (exact same assignment_type + family_status + employee_level combination)
- All currency-type benefits have a non-zero amount
- All tiers have a name

Show validation errors in a panel above the Publish button. Each error is a clickable link that scrolls to the offending cell/tier.

---

## API connections for this prompt

| Purpose | Endpoint |
|---|---|
| Save all benefit changes | `PUT /api/hr/policy-config/draft` |
| Get diff vs published | `GET /api/hr/policy-config/diff` |
| Revert a single row | `POST /api/hr/policy-config/draft/revert-row` |
| Get country list for overrides | `GET /api/suppliers/countries` |
| Get published version for comparison | `GET /api/hr/policy-config/published` |

### Key payload shape for a benefit row (`policy_config_benefits`):
```typescript
{
  benefit_key: string,             // e.g. "host_housing_cap"
  benefit_label: string,
  category: string,                // e.g. "compensation_allowances"
  covered: boolean,
  value_type: "currency" | "percentage" | "text" | "none",
  amount_value: number | null,
  currency_code: string | null,    // "EUR" | "USD" | "GBP" | "CHF"
  percentage_value: number | null,
  unit_frequency: "one_time" | "monthly" | "yearly" | "per_trip" | "per_day" | "per_dependent" | "custom",
  cap_rule_json: object | null,    // { cap_type, cap_value, cap_period, exceeds_behavior }
  conditions_json: object | null,
  assignment_types: string[],      // [] means all
  family_statuses: string[],       // [] means all
  employee_levels: string[],       // [] means all
  notes: string | null,
  display_order: number,
  is_active: boolean
}
```
