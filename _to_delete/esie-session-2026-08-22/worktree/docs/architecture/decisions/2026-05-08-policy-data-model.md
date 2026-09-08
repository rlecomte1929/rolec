# ADR 2026-05-08: Policy Data Model (Benefit Facts + Tier Snapshots)

**Status:** Accepted (with v1.1 schema adjustments — see "Test of the schema")
**Deciders:** Romain
**Companion diagrams:** [01-benefit-extraction](../diagrams/01-benefit-extraction.png), [02-policy-classification](../diagrams/02-policy-classification.png), [03-tier-snapshot-binding](../diagrams/03-tier-snapshot-binding.png), [04-assistant-scope-filtering](../diagrams/04-assistant-scope-filtering.png)

## Context

ReloPass v1 needs to represent HR mobility policies as queryable structured
data — both from template baselines and from customer-uploaded documents
(e.g. an "International Assignment Management" policy). The schema must
support tiered employee scoping, audit-traceable benefit facts (every value
points back to its source clause and the HR reviewer who confirmed it), and
a published-snapshot model so a case can be reasoned about against the exact
version of the policy that applied to it.

This ADR defines the v1 schema and tests it against five real clauses from
a TechnipFMC International Assignment Management policy. The fifth clause
is deliberately chosen to be awkward — to surface the seams in the schema
before code is written against it.

## Decision

### Hierarchy

A policy is a hierarchical structure:

- One **policy** per company (no per-employee or per-case policies in v1).
- Each policy is a **published snapshot** — immutable once published.
- Each policy contains **N benefits** (settling allowance, mobility
  premium, home leave, etc.).
- Each benefit holds **one or more benefit facts**, scoped by tier
  dimensions.
- Each benefit fact has: type, value, evidence, claim window, delivery,
  reviewer.
- An **employee case** binds to a policy snapshot at the employee's
  scope (company × tier values). All entitlement queries route through
  this binding.

### Schema (pseudocode)

```ts
Policy {
  id: uuid
  company_id: uuid
  version: string                      // e.g. "v3-2024"
  status: "draft" | "published" | "superseded"
  published_at: timestamp | null       // immutable once set
  effective_from: date
  effective_to: date | null
  document_source: {
    filename, version_label, page_count, sha256
  }
  tier_dimensions: TierDimension[]     // see below
  benefits: Benefit[]
}

TierDimension {
  name: string                         // "employee_grade", "family_status",
                                       // "assignment_type", "location_allowance_band"
  values: string[]                     // e.g. ["Director","Manager","Senior","Standard"]
  source: "company_tiers"              // values come from company HR config
        | "policy_derived"             // values come from the policy itself
        | "external_table"             // values come from a Country Addendum / external lookup
}

Benefit {
  id: uuid
  name: string                         // "Settling Allowance"
  category: "accommodation" | "cash" | "transport" | "leave"
          | "insurance" | "schooling" | "support" | "other"
  description: string
  source_citation: { section, page, quoted_text }
  facts: BenefitFact[]
  notes: string | null
}

BenefitFact {
  scope: { [tier_dimension: string]: string | { op: "==" | ">=" | "<=" | "in", value: any } }
                                       // e.g. { family_status: "Family",
                                       //        host_location_allowance_band: { op: ">=", value: 40 } }
  type: "cap" | "fixed" | "conditional" | "service" | "deferred" | "ambiguous"
  value: BenefitValue                  // shape depends on type — see below
  delivery: "reimbursement" | "direct_payment" | "payroll" | "in_kind"
  claim_window: { within: number, unit: "days"|"months", relative_to: string } | null
  excluded_when: Condition[] | null    // e.g. [{ dimension: "assignment_type", op: "==", value: "Localization" }]
  evidence: {
    source_citation: { section, page, quoted_text }
    extraction_confidence: 0..1        // from the AI extraction step
    reviewed_by: user_id | null        // null if not yet HR-reviewed
    reviewed_at: timestamp | null
  }
  notes: string | null
}

// Discriminated by BenefitFact.type:
BenefitValue =
  | Cap         { amount: number, currency: string, per_unit?: string, max_count?: number }
  | Fixed       { formula: { kind: "absolute" | "percent_of",
                             base?: "home_base_salary_gross" | "home_base_salary_net" | ...,
                             amount?: number, percent?: number },
                  cadence: "monthly" | "annual" | "one_off",
                  net_or_gross: "net" | "gross" }
  | Conditional { when: Condition[], then: BenefitValue, else?: BenefitValue }
  | Service     { provider: "host_entity" | "home_entity" | "vendor",
                  components: string[],         // e.g. ["flights_economy","hotel_max_3_nights"]
                  in_kind: boolean }
  | Deferred    { defined_in: "country_addendum" | "host_entity_decision" | "external_provider",
                  reason: string,               // why the master policy externalises the value
                  expected_dimensions: string[] }  // e.g. ["furnished_state","local_market"]
  | Ambiguous   { reason: string, manual_review_id: uuid }

Condition { dimension: string, op: "==" | ">=" | "<=" | "in", value: any }
```

### Lifecycle

- **Draft** policies can be edited; **published** snapshots cannot.
- A new version is published as a new snapshot; old snapshots remain
  queryable so historical cases retain their original entitlement basis.
- Cases bind to a snapshot at case creation. Re-binding to a newer
  snapshot is an explicit HR action with an audit event.

### Querying

- An employee case + a benefit name resolves to **at most one fact**
  by matching the case's tier values against `BenefitFact.scope`.
- If multiple facts match, the most-specific scope wins (more dimensions
  bound = more specific).
- If zero facts match, the response is **`not_configured`** with an
  escalation hint — never a silent default. (See diagram 03.)
- The assistant's retrieval layer (diagram 04) filters facts by the
  employee's scope **before** generation, so the model cannot see
  facts above the employee's tier.

## The five TechnipFMC clauses, mapped

Source: *International Assignment Management — Group Operating Principles /
Standards*. All quotes are verbatim. Section numbers refer to that
document.

### Clause 1: Mobility Premium — fixed (formula-based)

> "For STA and LTA, a premium is given which represents 10% of the
> Home Country gross base salary. It is granted as a compensation to
> work abroad. It is paid on a monthly basis as a net amount." (§ 8.1)

- Mapped to: **Mobility Premium** (category: `cash`)
- Type: `fixed`
- Value: `{ formula: { kind: "percent_of", base: "home_base_salary_gross", percent: 10 }, cadence: "monthly", net_or_gross: "net" }`
- Tier scope: `{ assignment_type: { op: "in", value: ["STA","LTA"] } }` — explicitly *not* paid for ECD or Localization.
- Delivery: `payroll`
- Source citation: § 8.1
- Notes: The percentage is non-tiered by employee grade in the master
  policy. It **is** tiered by `assignment_type`. This is the first hint
  that the v1 tier dimension Director/Manager/Senior/Standard from
  diagram 03 isn't sufficient on its own — see "Test of the schema".

### Clause 2: Pre-Assignment Visit — service / non-monetary

> "Assignee and partner are allowed to have 1 pre-assignment visit to
> the Host location, arranged and paid by the Host Entity, under the
> following rules: ... In case flights are needed, this will be in
> economy class, Hotel for maximum 3 nights will be reimbursed based
> on the Host Entity travel policy ..." (§ 9.2)

- Mapped to: **Pre-Assignment Visit** (category: `support`)
- Type: `service`
- Value: `{ provider: "host_entity", in_kind: true, components: ["flights_economy_return", "hotel_max_3_nights", "workdays_charged_to_host"] }`
- Tier scope: `{ assignment_type: "LTA" }` — STA, ECD, and construction site assignments are excluded.
- Delivery: `in_kind`
- Excluded when: `[{ dimension: "assignment_subtype", op: "==", value: "construction_site" }]`
- Source citation: § 9.2
- Notes: A nested cap ("max 3 nights") lives inside `components` as a
  string token. The schema accepts this loosely. If we later need to
  query "how many hotel nights does X get?" we'll regret encoding it as
  a string — see "Test of the schema".

### Clause 3: Home Leaves Frequency — conditional, multi-dimensional

> "Family — once per year of assignment; two per year of assignment
> for countries where the location allowance equals or exceeds 40%
> (assignee and family members)." (§ 10.5.1)

- Mapped to: **Home Leave Frequency** (category: `leave`)
- Type: `conditional`
- Value: `{ when: [{ dimension: "family_status", op: "==", value: "Family" }, { dimension: "host_location_allowance_pct", op: ">=", value: 40 }], then: { type: "fixed", count: 2, unit: "round_trip", per: "year_of_assignment" }, else: { type: "fixed", count: 1, unit: "round_trip", per: "year_of_assignment" } }`
- Tier scope: `{ family_status: "Family" }` — the same benefit has a
  separate fact for `family_status ∈ {Single, Split}` ("every 3 months
  of assignment"), held as a sibling row.
- Delivery: `in_kind` (flight tickets via corporate fares)
- Source citation: § 10.5.1
- Notes: This is the canonical conditional. The condition mixes a
  *company-tier* dimension (`family_status`) with a *policy-derived*
  dimension (`host_location_allowance_pct`) that depends on the host
  country. The schema must allow both kinds of dimensions in the same
  condition — see "Test of the schema".

### Clause 4: Storage Insurance — multi-axis cap

> "Maximum 5 m³ (both Single and Family status) ... Single Status:
> Maximum EUR 1,000 per m³ ... Family Status: Maximum EUR 2,000 per
> m³ ... Note: in case of storage, the amount is per month." (§ 9.3)

- Mapped to: **Storage Insurance** (category: `accommodation`)
- Type: `cap` (two facts — one per family_status row)
- Value (Single): `{ amount: 1000, currency: "EUR", per_unit: "m3_per_month", max_count: 5, max_count_unit: "m3" }`
- Value (Family): `{ amount: 2000, currency: "EUR", per_unit: "m3_per_month", max_count: 5, max_count_unit: "m3" }`
- Tier scope: `{ family_status: "Single" }` and `{ family_status: "Family" }` respectively
- Delivery: `direct_payment` (insurance contract)
- Source citation: § 9.3 (storage table)
- Notes: A single benefit needing two stacked dimensions — *volume*
  (5 m³) and *cost per unit* (€1,000 or €2,000 per m³ per month). The
  schema's `Cap` shape carries both, but the second per-unit suffix
  ("per month") is mashed into a string. This is workable but not
  elegant. Acceptable for v1.

### Clause 5: Settling Allowance — the awkward one

> "Furthermore, a settling allowance will be paid by the Host Entity,
> in order to cover minimum expenses with furniture, utensils, home
> clothes, etc. The amount is defined by the Host Entity depending
> on whether accommodation is furnished or unfurnished considering
> local market conditions. The final request of reimbursement has
> to be made within a 3-month maximum delay." (§ 10.1)

> "In the case of Localization, temporary accommodation may be
> considered and there will be no settling allowance." (§ 10.1)

- Mapped to: **Settling Allowance** (category: `accommodation`)
- Type: **`deferred`** — the master policy explicitly externalises the amount.
- Value: `{ defined_in: "country_addendum", reason: "amount set by Host Entity by furnished_state and local market conditions", expected_dimensions: ["furnished_state", "host_country"] }`
- Tier scope: assignments where `assignment_type ∈ {LTA}` and `assignment_subtype != "construction_site"` (the settling allowance applies in support of relocation; for assignments under 12 months § 10.1 covers hotel/aparthotel instead).
- Delivery: `reimbursement`
- Claim window: `{ within: 3, unit: "months", relative_to: "expense_incurred" }`
- Excluded when: `[{ dimension: "assignment_type", op: "==", value: "Localization" }]`
- Source citation: § 10.1
- Notes: Diagram 01 used the example "Settling allowance: €5,000". The
  real master policy specifies *no amount at all* — it defers entirely
  to the Country Addendum. This forced the schema change described
  below.

## Test of the schema

After mapping the five clauses, the schema as originally drawn in the
diagrams (cap / fixed / conditional / service / ambiguous, plus a
single `employee_grade` tier dimension) needed three adjustments
before all five clauses fit cleanly:

| # | Schema needed to | Triggered by |
|---|------------------|--------------|
| 1 | Add a 6th type: **`deferred`** (value defined in a Country Addendum or external table, not in the master policy itself). | Clause 5 — settling allowance has no amount in the master policy at all. The original 5 categories had no way to express "the policy is clear; the value is just elsewhere". Treating it as `ambiguous` would have been wrong (nothing is unclear) and treating it as `cap` or `fixed` would have invented an amount. |
| 2 | Move `claim_window` and `excluded_when` to **orthogonal fields** on `BenefitFact`, instead of trying to encode them inside the `value`. | Clause 5 — the 3-month reimbursement deadline and the Localization exclusion are cross-cutting concerns that apply regardless of value type. Forcing them inside the value shape would have polluted every value variant. |
| 3 | Allow `tier_dimensions` to mix **company tiers** (Director/Manager/Senior/Standard, family_status) with **policy-derived** dimensions (`assignment_type`, `host_location_allowance_pct`). | Clause 1 (assignment_type), Clause 3 (location_allowance_band as a derived condition), Clause 4 (family_status). Diagram 03's tier table is an instance of this, not the whole story. The Director/Manager/Senior/Standard slice is one dimension among several. |

**Did the schema accept all five cleanly?** No — and that is the
useful answer. Three real seams surfaced. The schema above is the v1.1
version with the three adjustments applied. All five clauses now map
to it without fabricating values or losing fidelity.

**A finding the diagrams should absorb**: diagram 03 ("Tier-snapshot
binding") shows a single tier dimension (Director/Manager/Senior/
Standard). The real policy needs **multi-dimensional tiering** —
employee grade AND family status AND assignment type AND, for some
benefits, host-country-derived bands. The diagram is not wrong, but
it's a single slice of a larger structure. When this ADR ships,
diagram 03 should either gain a small note ("tier dimensions can
compose; see ADR 2026-05-08") or be redrawn against a multi-dimensional
example. I am not redrawing it in this PR — that's a separable
follow-up.

**A finding the implementation should absorb**: nested constraints
inside `Service.components` (e.g. "hotel_max_3_nights") are encoded as
strings in v1. This is acceptable for entitlement *answers* (HR can
read the string), but if the assistant or HR command center ever needs
to *query* "how many nights?" we'll need to decompose. Flagged for v1.x.

## Consequences

- **Sprint A** builds the benefit-fact extraction + HR validation flow
  (diagrams 01 and 02) against this v1.1 schema. The `deferred` type
  is a first-class category in the HR review UI, not an "ambiguous"
  fallback.
- **Sprint B** builds the published-snapshot binding (diagram 03) and
  the `not_configured + escalation` response path. Multi-dimensional
  tier resolution lives here.
- **Sprint C** builds the assistant retrieval layer (diagram 04) with
  scope filtering, typed refusals, and audit logging.
- **Override layer** (per-employee deviations from tier values) is
  intentionally deferred to v3. The v1 schema reserves no field for
  it. v3 will add an `OverrideFact` linked to a specific case_id;
  resolution will prefer override fact > snapshot fact > not_configured.
- The schema captures **only** mobility / relocation policies. Other
  HR policy types (parental leave, expense, code of conduct) are out
  of scope for v1.
- **Country Addenda** are referenced by the master policy as the
  resolver for `deferred` facts. v1 stores Country Addenda as
  separate, lighter-weight policy objects keyed by
  `(company_id, country_code)`, with the same fact structure but no
  tier hierarchy. A `deferred` fact in the master policy resolves at
  query time by looking up the matching Country Addendum fact.

## Alternatives considered

- **Per-employee policies** (one policy object per case). Rejected:
  policy sprawl, inconsistent entitlement logic across the same
  company, weak audit trail. (Diagram 03, "Rejected design".)
- **Free-text policy storage with retrieval-only access** (no
  structured facts; assistant always reads the document). Rejected:
  it makes the "is X within the package?" check impossible to
  answer deterministically, and prevents the not_configured-vs-
  configured distinction that drives escalation in diagram 04.
- **Treating `deferred` as just `ambiguous`**. Rejected after Clause
  5 — see "Test of the schema". `ambiguous` should mean "the policy
  is unclear and a human must decide what was meant". A clause that
  cleanly defers to an external table is not ambiguous; it's
  resolved-elsewhere. Conflating the two would dilute the manual
  review queue (diagram 01).
- **Single-dimensional tiering** (just employee grade). Rejected
  after Clauses 1, 3, and 4 — three of the five real clauses tier
  on dimensions other than employee grade.

---

## Reconciliation log

**2026-05-08 (later same day):** The schema test in this ADR surfaced that diagram 03's single-dimension tier table (Director / Manager / Senior / Standard) was one slice of a larger structure. Real Technip clauses require multi-dimensional tier composition — for example, "two home leave trips per year for countries where the location allowance ≥ 40%" is keyed by host-country band, not employee grade. Diagram 03 has been redrawn to reflect this in PR #103, with `tier_composition = (employee_grade, family_status, assignment_type, host_country_allowance_band)`.

Three implicit decisions visible in earlier drafts of the redrawn diagram (resolution rule, case-binding rule, blank-cell handling beyond "not configured + escalation") were intentionally removed before commit and remain unspecified. They are the scope of a follow-up ADR before Sprint A begins.