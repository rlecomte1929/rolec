# Comparison readiness and employee fallback

This document defines when employee-side **policy comparison** (cost bars, service-vs-policy comparison, and eligibility-style badges) is allowed, and what employees see otherwise.

Related: [minimum-normalized-policy-schema.md](./minimum-normalized-policy-schema.md) (ComparisonReadiness), [metadata-vs-decision-layer.md](./metadata-vs-decision-layer.md), [services-page-policy-consumption.md](./services-page-policy-consumption.md) (Services UI), [policy-degraded-states.md](./policy-degraded-states.md) (HR + employee state matrix).

---

## 1. Exact conditions for `comparison_ready`

Employee comparison is gated on **all** of the following:

1. **Matching published company policy** — Resolution finds a `company_policies` row for the assignment context (case / HR company / employee profile company), with a **`policy_versions` row in `status = 'published'`** (see `policy_resolution.find_first_published_company_policy`).
2. **Resolved snapshot exists** — `resolved_assignment_policies` can be built for the assignment (same path as today).
3. **Layer-2 structural readiness** — The published `policy_version_id` passes `evaluate_version_comparison_readiness` in `backend/services/policy_comparison_readiness.py`.

### 3.1 What `evaluate_version_comparison_readiness` checks

- Loads `policy_versions` by id; requires **`status == 'published'`** (defense in depth; employee resolution already uses published versions only).
- Loads `policy_benefit_rules` for that version.
- For each benefit key in **`EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS`**:

  `temporary_housing`, `schooling`, `shipment`

  there must be **at least one** rule row for that `benefit_key` with a **decision signal**:

  - `amount_value` &gt; 0, **or**
  - `metadata_json` numeric `max_value` / `standard_value` / `min_value` &gt; 0, **or**
  - `metadata_json.approval_required === true`, **or**
  - `metadata_json.allowed === false` (explicit exclusion / not allowed).

If any required key is missing or has no qualifying rule, `comparison_ready` is **false** and `comparison_blockers` lists codes such as:

- `MISSING_COMPARISON_CATEGORY:<benefit_key>`
- `COVERED_WITHOUT_DECISION_FIELDS:<benefit_key>`
- `NOT_PUBLISHED` / `MISSING_POLICY_VERSION` / `NO_MATCHING_PUBLISHED_POLICY` (when no published version or assignment resolution fails)

### 1.1 Relation to the minimum schema’s full `comparison_ready`

The canonical schema ([§6.2](./minimum-normalized-policy-schema.md)) describes a **stricter** surface (six wizard categories including banks and insurances). The **product gate implemented in code** currently requires the **three** keys above so that:

- **Package summary** cost comparison (housing / schools / movers caps) does not run on incomplete data.
- Tenants are not blocked solely because banking or insurance rows are absent while core relocation caps are fully normalized.

Extending `EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS` to match all `SERVICE_TO_BENEFIT` keys (e.g. `banking_setup`, `insurance`) is a deliberate product change.

---

## 2. What the employee sees when `comparison_ready` is false

### 2.1 APIs

| Endpoint | Behavior |
|----------|----------|
| `GET .../policy-budget` | `has_policy` may still be **true**; **`comparison_available`: false**; **`caps`: {}**; includes `comparison_readiness`. |
| `GET .../policy-service-comparison` | **`comparisons`: []**; **`comparison_available`: false**; short `message`; **`comparison_readiness`** present. |
| `GET .../policy-envelope` | If `has_policy` and not `comparison_available`: **`benefits` / `exclusions` / `envelopes` cleared** (no envelope cards). |
| `GET .../policy`, `GET .../me/assignment-package-policy` | Full resolution may still return benefits for HR/debug; **`comparison_available`** and **`comparison_readiness`** are set. Frontend **must not** show eligibility badges when `comparison_available === false`. |

### 2.2 UI copy (static)

Aligned with `frontend/src/features/policy/employeePolicyMessages.ts`:

- **Primary:** Your company policy has not yet been published in a form that supports cost comparison.
- **Secondary:** You can still review service costs, but company coverage and limits are not available yet.

### 2.3 Screens

- **Package summary (`PackageSummary`)** — Selected services and **cost labels only**; **no** “HR Policy Comparison” bars; shows the notice when `has_policy && !comparison_available`.
- **Assignment Package & Limits (`EmployeeResolvedPolicyView`)** — Notice + optional “Policy on file” title; **no** category cards or Covered / Partially covered badges.
- **Compact policy (`EmployeePolicyView`)** — Same notice path when resolved policy exists but comparison is unavailable.

---

## 3. What the employee sees when `comparison_ready` is true

- **`comparison_available`: true** on policy and budget responses.
- **`GET .../policy-budget`** returns **non-empty caps** when resolved benefits support them (same as before).
- **Package summary** shows **HR Policy Comparison** bars (covered vs extra) when caps load.
- **Policy / package views** show **resolved benefits** with **eligibility-style badges** as today.
- **`GET .../policy-service-comparison`** returns **per-service comparisons** (employee); HR endpoint unchanged and **not** gated.

---

## 4. Implementation map

| Piece | Location |
|-------|----------|
| Readiness evaluation | `backend/services/policy_comparison_readiness.py` |
| Attached to resolution | `backend/main.py` — `_finalize_employee_policy_resolution` |
| Comparison engine gate | `backend/services/policy_service_comparison.py` — `employee_gate=True` |
| Employee copy | `frontend/src/features/policy/employeePolicyMessages.ts` |
