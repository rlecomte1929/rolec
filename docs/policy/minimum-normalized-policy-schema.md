# Minimum normalized policy schema

**Purpose:** Canonical **minimum** JSON shape the normalization pipeline (or a post-normalize materialization step) must be able to produce so the employee app can answer: *in-scope services*, *coverage*, *limits*, *eligibility gates*, and *whether the cost comparison engine may run*.

**Principles**

- Small surface area; no attempt to model every clause type.
- **Stable string keys** for categories (snake_case). Same keys in `service_categories` and `coverage_rules`.
- **Provenance** is optional but recommended; never required for `comparison_ready`.
- This document is the contract; persistence may be DB tables, a `jsonb` column on `policy_versions`, or a generated artifact—as long as the emitted object conforms.

**Relation to code today**

- Comparison maps wizard **service categories** → **benefit keys** in `backend/services/policy_service_comparison.py` (`SERVICE_TO_BENEFIT`). This schema uses **`category_key`** aligned to that map where possible, plus extra policy-native categories (e.g. `immigration`, `tax`) for HR/eligibility UX.
- Long term, normalization should emit one object (or merge into resolved policy) satisfying this schema.

---

## 1. Root object: `MinimumNormalizedPolicy`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | `string` | **Yes** | Contract version, e.g. `"1.0.0"`. |
| `identity` | `PolicyIdentity` | **Yes** | §2 |
| `service_categories` | `ServiceCategoryEntry[]` | **Yes** | §3 — in-scope matrix |
| `coverage_rules` | `CoverageRule[]` | **Yes** | §4 — limits & coverage (may be empty only if every category is `not_allowed`; see §6) |
| `eligibility` | `EligibilityBundle` | **Yes** | §5 — gates applying to the package (may be empty objects) |
| `comparison` | `ComparisonReadiness` | **Yes** | §6 |

---

## 2. `PolicyIdentity` (section A)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `policy_id` | `string` (uuid) | **Yes** | `company_policies.id` |
| `policy_version_id` | `string` (uuid) | **Yes** | `policy_versions.id` |
| `company_id` | `string` | **Yes** | Tenant |
| `title` | `string` | **Yes** | Human-readable policy title |
| `policy_scope` | `string` | **Yes** | Document/policy scope, e.g. `long_term_assignment`, `short_term_assignment`, `global`, `tax_equalization`, `mixed`, `unknown` (align with `policy_documents.detected_policy_scope` enums where possible). |
| `effective_date` | `string` (ISO date) \| `null` | No | `YYYY-MM-DD` if known |
| `published` | `boolean` | **Yes** | `true` iff this version is the employee-visible published revision |
| `source_policy_document_id` | `string` (uuid) \| `null` | No | Traceability to intake document |

---

## 3. `ServiceCategoryEntry` — supported service categories (section B)

Represents **product-facing** service buckets (wizard / services UX), not every raw `benefit_key` in taxonomy.

### 3.1 `category_key` (recommended enum)

Minimum set the pipeline should **populate** (use `unknown` eligibility if the document is silent):

| `category_key` | Notes |
|----------------|--------|
| `immigration` | Visas, work permits |
| `movers` | Household goods / shipment (maps to `shipment` in comparison) |
| `housing` | Longer-term housing / allowance (often maps to `temporary_housing` in engine) |
| `temporary_housing` | Interim / temp accommodation |
| `schools` | Education / tuition (maps to `schooling`) |
| `tax` | Tax equalization / assistance |
| `travel` | Flights, home leave, business travel |
| `settling_in` | Settling-in / one-off allowances |
| `spouse_support` | Partner / spouse support |
| `banking` | Bank setup (maps to `banking_setup`) |
| `insurance` | Health / travel insurance (maps to `insurance`) |
| `medical` | Medical beyond generic insurance if distinct |
| `household_goods` | If separated from `movers` in your UX |
| `repatriation` | Return / end-of-assignment |
| `other` | Catch-all |

**Comparison-critical subset** (must appear in `service_categories[]` for a full comparison pass — see §6):

`housing`, `living_areas`, `schools`, `movers`, `banks`, `insurances`

- Use **`living_areas`** as the wizard key for housing-like benefits if that is what `SERVICE_TO_BENEFIT` expects.
- Use **`banks`** not `banking` if you target the current map; or emit both entries with the same eligibility/coverage if needed.

### 3.2 Object shape

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category_key` | `string` | **Yes** | One of the table above or product-approved extension |
| `eligibility` | `enum` | **Yes** | `allowed` \| `not_allowed` \| `unknown` |
| `confidence` | `number` | **Yes** | `0.0`–`1.0` (use `0.5` if heuristic / default) |
| `evidence` | `EvidenceRef[]` | No | §3.3 — clause / page pointers |

### 3.3 `EvidenceRef`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | `string` | **Yes** | e.g. `policy_document_clause`, `policy_benefit_rule`, `manual_hr` |
| `id` | `string` | No | Clause id, rule id, etc. |
| `label` | `string` | No | Short human label |
| `page_start` | `number` | No | PDF page |
| `page_end` | `number` | No | PDF page |

---

## 4. `CoverageRule` — coverage / benefit rules (section C)

One row per **`category_key`** you describe coverage for (typically one per `allowed` category; **required** for each `allowed` category when `comparison_ready` must be true — §6).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category_key` | `string` | **Yes** | Must match a `service_categories[].category_key` |
| `benefit_key` | `string` \| `null` | No | Canonical taxonomy key for engine mapping (e.g. `temporary_housing`, `schooling`, `shipment`) |
| `covered` | `boolean` | **Yes** | `false` = explicitly not covered / excluded for this category |
| `cap_amount` | `number` \| `null` | No | Single primary cap for comparison (prefer **max** or policy **standard** — document which you use in `cap_basis`) |
| `cap_basis` | `string` | No | `max` \| `standard` \| `min` \| `unspecified` — which policy number `cap_amount` represents |
| `currency` | `string` (ISO 4217) | No | Default `USD` if omitted only when no monetary cap |
| `cap_unit` | `string` \| `null` | No | e.g. `per_assignment`, `per_month`, `per_year`, `days`, `percent_salary` |
| `payment_mode` | `enum` | No | `reimbursement` \| `direct_pay` \| `allowance` \| `unknown` |
| `employee_contribution` | `object` \| `null` | No | `{ "type": "percent" \| "flat" \| "unknown", "value": number \| null }` if stated |
| `approval_required` | `boolean` | **Yes** | Default `false` if unstated |
| `notes` | `string` | No | Short free text for HR/employee UI |

**Rules**

- If `covered === false`, `cap_amount` should be `null`; comparison uses exclusion path.
- If `covered === true` and numeric comparison is desired, set `cap_amount` + `currency` when the source states a number; otherwise comparison may still run in “qualitative” mode (see §6).

---

## 5. `EligibilityBundle` — conditions (section D)

Package-level gates. All sub-objects are **optional**; use empty arrays or omit keys if unknown.

### 5.1 Shape

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assignment_types` | `AssignmentTypeCondition` | No | §5.2 |
| `family_status` | `FamilyStatusCondition` | No | §5.3 |
| `duration` | `DurationCondition` \| `null` | No | §5.4 |
| `job_level` | `JobLevelCondition` \| `null` | No | §5.5 |
| `geography` | `GeographyCondition` \| `null` | No | §5.6 |
| `exclusions` | `ExclusionSummary[]` | No | §5.7 |

### 5.2 `AssignmentTypeCondition`

| Field | Type | Required |
|-------|------|----------|
| `allowed_values` | `string[]` | **Yes** if object present — e.g. `["LTA","STA"]` (normalized codes) |
| `confidence` | `number` | **Yes** |

### 5.3 `FamilyStatusCondition`

| Field | Type | Required |
|-------|------|----------|
| `allowed_values` | `string[]` | **Yes** if present — e.g. `["single","accompanied","with_children"]` |
| `confidence` | `number` | **Yes** |

### 5.4 `DurationCondition`

| Field | Type | Required |
|-------|------|----------|
| `min_months` | `number` \| `null` | No |
| `max_months` | `number` \| `null` | No |
| `confidence` | `number` | **Yes** if object present |

### 5.5 `JobLevelCondition`

| Field | Type | Required |
|-------|------|----------|
| `tiers_allowed` | `string[]` \| `null` | Band/grade labels if stated |
| `confidence` | `number` | **Yes** if object present |

### 5.6 `GeographyCondition`

| Field | Type | Required |
|-------|------|----------|
| `host_countries_allowlist` | `string[]` \| `null` | ISO or names as extracted |
| `host_countries_denylist` | `string[]` \| `null` | Excluded destinations |
| `confidence` | `number` | **Yes** if object present |

### 5.7 `ExclusionSummary`

| Field | Type | Required |
|-------|------|----------|
| `category_key` | `string` \| `null` | Target category if specific |
| `summary` | `string` | **Yes** | One-line description |
| `evidence` | `EvidenceRef[]` | No |

---

## 6. `ComparisonReadiness` (section E)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `comparison_ready` | `boolean` | **Yes** | Machine gate: may the employee comparison engine run? |
| `comparison_blockers` | `string[]` | **Yes** | Empty if `comparison_ready === true`. Standard codes below. |
| `partial_numeric_coverage` | `boolean` | No | `true` if some allowed categories lack caps but comparison still allowed |

### 6.1 Standard `comparison_blocker` codes

| Code | Meaning |
|------|---------|
| `NOT_PUBLISHED` | `identity.published !== true` |
| `MISSING_IDENTITY` | Missing any mandatory `identity` field |
| `NO_SERVICE_CATEGORIES` | `service_categories` empty |
| `MISSING_COMPARISON_CATEGORY:<key>` | Required comparison key (§6.2) absent from `service_categories` |
| `ALLOWED_WITHOUT_COVERAGE_RULE:<key>` | Category `eligibility === allowed` but no `coverage_rules` row for `category_key` |
| `COVERAGE_UNDECIDED:<key>` | `coverage_rules` row exists but `covered` cannot be determined (should not happen if pipeline forces boolean) |
| `ENGINE_UNMAPPED:<key>` | Category allowed & covered but no `benefit_key` and no static map to comparison engine |
| `ELIGIBILITY_UNKNOWN:<key>` | Strict mode: a comparison-required category is still `unknown` (product-defined) |
| `COVERED_WITHOUT_DECISION_FIELDS:<key>` | `covered === true` but no cap, no `approval_required`, and no acceptable qualitative signal (§6.2) |
| `POLICY_AMBIGUOUS` | Product-level: HR must confirm before compare (optional use) |

### 6.2 Required keys for “full” comparison readiness

For `comparison_ready === true` in the **strict** sense (numeric / included compare for core relocation services), **all** of the following must hold:

1. **Identity** — `policy_id`, `policy_version_id`, `company_id`, `title`, `policy_scope`, `published` are set; `published === true`.
2. **Service matrix** — `service_categories` includes an entry for **each** of:

   `housing`, `living_areas`, `schools`, `movers`, `banks`, `insurances`

   (six keys — matches current `SERVICE_TO_BENEFIT` / wizard surface.)

3. **Coverage pairing** — For every category where `eligibility === allowed`:

   - There is a `coverage_rule` with the same `category_key`,
   - `covered` is set,
   - If `covered === true`, at least one of:
     - `cap_amount` is a non-null number (with `currency` recommended), **or**
     - `approval_required === true` (comparison runs but flags approval), **or**
     - `payment_mode !== unknown` with explicit `notes` for qualitative compare (product may still set `partial_numeric_coverage: true`).

4. **Blockers** — `comparison_blockers` is `[]`.

If you allow comparison with **exclusions only** (no caps), set `partial_numeric_coverage: true` and do **not** emit `ALLOWED_WITHOUT_COVERAGE_RULE`; still require `covered` boolean per allowed category.

### 6.3 Relaxed readiness (optional product mode)

You may define a second flag (not required in v1) e.g. `comparison_ready_soft` if the product allows running the engine with missing categories and only surfacing `comparison_blockers` as warnings. **This schema only standardizes `comparison_ready` + `comparison_blockers` as the hard gate.**

---

## 7. Mandatory vs optional summary

| Section | Always required |
|---------|-----------------|
| `schema_version`, `identity.*` (mandatory fields), `service_categories` (non-empty), `coverage_rules` (array, may be empty only if no `allowed` categories), `eligibility` (object), `comparison` | Yes |
| `effective_date`, `source_policy_document_id`, evidence arrays, `benefit_key`, monetary fields, `eligibility` sub-conditions | No |
| `comparison.partial_numeric_coverage` | No |

---

## 8. Minimal valid JSON example

```json
{
  "schema_version": "1.0.0",
  "identity": {
    "policy_id": "550e8400-e29b-41d4-a716-446655440000",
    "policy_version_id": "660e8400-e29b-41d4-a716-446655440001",
    "company_id": "acme-corp-uuid",
    "title": "Long-term assignment policy summary",
    "policy_scope": "long_term_assignment",
    "effective_date": null,
    "published": true,
    "source_policy_document_id": "770e8400-e29b-41d4-a716-446655440002"
  },
  "service_categories": [
    { "category_key": "movers", "eligibility": "allowed", "confidence": 0.7, "evidence": [] },
    { "category_key": "schools", "eligibility": "allowed", "confidence": 0.65, "evidence": [] },
    { "category_key": "living_areas", "eligibility": "allowed", "confidence": 0.5, "evidence": [] },
    { "category_key": "banks", "eligibility": "not_allowed", "confidence": 0.6, "evidence": [] },
    { "category_key": "insurances", "eligibility": "allowed", "confidence": 0.55, "evidence": [] }
  ],
  "coverage_rules": [
    {
      "category_key": "movers",
      "benefit_key": "shipment",
      "covered": true,
      "cap_amount": 10000,
      "cap_basis": "max",
      "currency": "USD",
      "cap_unit": "per_assignment",
      "payment_mode": "reimbursement",
      "employee_contribution": null,
      "approval_required": false,
      "notes": null
    },
    {
      "category_key": "schools",
      "benefit_key": "schooling",
      "covered": true,
      "cap_amount": 20000,
      "cap_basis": "max",
      "currency": "USD",
      "cap_unit": "per_year",
      "payment_mode": "reimbursement",
      "employee_contribution": null,
      "approval_required": true,
      "notes": null
    },
    {
      "category_key": "banks",
      "benefit_key": "banking_setup",
      "covered": false,
      "cap_amount": null,
      "cap_basis": "unspecified",
      "currency": "USD",
      "cap_unit": null,
      "payment_mode": "unknown",
      "employee_contribution": null,
      "approval_required": false,
      "notes": "Not covered for this band"
    },
    {
      "category_key": "insurances",
      "benefit_key": "insurance",
      "covered": true,
      "cap_amount": null,
      "cap_basis": "unspecified",
      "currency": "USD",
      "cap_unit": null,
      "payment_mode": "direct_pay",
      "employee_contribution": null,
      "approval_required": false,
      "notes": "Covered; no numeric cap in summary"
    }
  ],
  "eligibility": {
    "assignment_types": { "allowed_values": ["LTA"], "confidence": 0.7 },
    "family_status": { "allowed_values": ["accompanied", "single"], "confidence": 0.5 },
    "duration": null,
    "job_level": null,
    "geography": null,
    "exclusions": []
  },
  "comparison": {
    "comparison_ready": false,
    "comparison_blockers": [
      "MISSING_COMPARISON_CATEGORY:housing",
      "ALLOWED_WITHOUT_COVERAGE_RULE:living_areas",
      "COVERED_WITHOUT_DECISION_FIELDS:insurances"
    ],
    "partial_numeric_coverage": true
  }
}
```

*(Example intentionally fails strict readiness: missing `housing` row, `living_areas` allowed but no `coverage_rule`, `insurances` covered with no cap and `approval_required: false`.)*

---

## 9. Next implementation step (out of scope for this file)

1. After normalize (or on publish), **materialize** this object (validate, set `comparison_*`).
2. Align `category_key` ↔ `SERVICE_TO_BENEFIT` in one place.
3. Employee comparison reads **this** artifact or a DB projection identical in shape.

---

*Schema version: **1.0.0** — bump `schema_version` when adding required fields or changing `comparison_ready` rules.*
