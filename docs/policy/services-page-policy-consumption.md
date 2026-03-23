# Employee Services page — policy consumption

How the **Services** (`ProvidersPage`) screen uses **normalized, published** HR policy output. It does **not** read `policy_documents.extracted_metadata`, clause `normalized_hint_json`, or other Layer‑1 extraction fields.

---

## 1. Data source (Layer 2 only)

| Concern | Source |
|--------|--------|
| API | `GET /api/employee/assignments/{assignment_id}/services-policy-context` |
| Server builder | `backend/services/employee_services_policy_context.py` → `build_employee_services_policy_context` |
| Input | Result of `_resolve_published_policy_for_employee` (same path as `/policy`, `/policy-budget`) |
| Benefit rows | `resolved_assignment_policy` → `list_resolved_policy_benefits` (`benefit_key`, `included`, caps, `approval_required`, `condition_summary`, …) |
| Global comparison gate | `comparison_available` / `comparison_readiness` (see [comparison-readiness-and-fallback.md](./comparison-readiness-and-fallback.md)) |

The response includes `source: "resolved_assignment_policy"` so clients can assert they are not using raw document metadata.

---

## 2. Wizard category mapping

Enabled services declare `backendKey` in `frontend/src/features/services/serviceConfig.ts`. Those keys map to canonical **`benefit_key`** values using the same table as the comparison engine: `SERVICE_TO_BENEFIT` in `backend/services/policy_service_comparison.py`.

| Service (UI) | `backendKey` | `benefit_key` | Notes |
|--------------|--------------|---------------|--------|
| Housing | `living_areas` | `temporary_housing` | Same mapping as wizard `housing` / `living_areas` |
| Movers | `movers` | `shipment` | |
| Schools | `schools` | `schooling` | |
| Banking | `banks` | `banking_setup` | |
| Insurance | `insurance` | `insurance` | Config uses `insurance` (singular) |
| Electricity | `electricity` | — | **out_of_scope** for relocation comparison |

---

## 3. Per-category `determination`

For each wizard key in `SERVICES_WIZARD_KEYS`, the backend picks a **primary** resolved benefit row for that `benefit_key` (`_best_benefit_for_key`) and sets:

| `determination` | When | Employee meaning |
|-----------------|------|-------------------|
| `no_published_policy` | `has_policy === false` | No linked published policy for this assignment |
| `no_benefit_rule` | Policy exists, no row for this `benefit_key` | Policy does not define this benefit in structured rules |
| `excluded` | Row exists, `included === false` | **Not covered** — only shown when resolution says so |
| `capped` | Included, numeric cap from `max_value` / `standard_value` / `min_value` | Limit is known from policy |
| `approval_required` | Included, no usable cap, `approval_required` | Pre-approval path |
| `capped_with_approval` | Included, cap + approval | Limit and approval both apply |
| `included_partial` | Included, no cap and no approval flag | Covered in principle; machine-readable limit not available |
| `out_of_scope` | Electricity (no `benefit_key`) | Outside standard relocation policy comparison |

---

## 4. `show_policy_comparison` (ribbon / strong affordance)

`show_policy_comparison` is **true** only when:

1. **`comparison_available === true`** (global comparison-ready gate), **and**
2. Benefit is **included**, **and**
3. There is a **numeric cap line** or **`approval_required`**.

So:

- **Global comparison off** → never `true` (cost-summary-only mode for comparison UI; see §5).
- **Excluded** → never `true` (we show exclusion copy, not a comparison ribbon).
- **Partial** (`included_partial`) → `false`; card uses **partial** styling and copy.

The frontend maps `show_policy_comparison` to the **green “compare”** border on the service card (`ServiceCard`).

---

## 5. Page-level behavior (`no_policy` / `partial-policy` / `comparison-ready`)

| State | Condition | Services page |
|-------|-----------|----------------|
| **No policy** | `has_policy === false` | Banner: HR has not published policy (shared copy). Per-category hints use `no_published_policy` where applicable. **No** speculative caps. |
| **Partial policy (global)** | `has_policy === true` && `comparison_available === false` | Banner: policy not yet comparison-ready ([comparison-readiness](./comparison-readiness-and-fallback.md)). Cards still show **excluded** / **partial** / **no rule** from resolved benefits when trustworthy; **no** green comparison ribbon. |
| **Comparison-ready** | `comparison_available === true` | Green **“Company policy comparison is active”** ribbon. Eligible categories show **policy limit / approval** line with compare styling. |

---

## 6. Frontend wiring

| Piece | Role |
|-------|------|
| `employeeAPI.getServicesPolicyContext` | Fetches context; failures are non-fatal (Services still load). |
| `ProvidersPage` | Loads context in parallel with assignment services; builds `policyHintForItem` from `categories[backendKey]`. |
| `ServiceGroupSection` | Passes hint into each `ServiceCard`. |
| `ServiceCard` | Renders a **single** policy line under the description; variant from `determination` + `show_policy_comparison`. |

---

## 7. Explicit non-goals

- Do **not** call policy-document intake metadata endpoints for Services UX.
- Do **not** infer coverage from `mentioned_*` or PDF titles.
- Do **not** treat platform default caps (`/policy/caps`) as company policy; Services uses **resolved** payload only (currency may still fall back to defaults only when context request fails).

---

## 8. Related docs

- [published-policy-consumption-rules.md](./published-policy-consumption-rules.md) — publish gate; only **published** normalized versions are consumable  
- [comparison-readiness-and-fallback.md](./comparison-readiness-and-fallback.md) — global `comparison_available` rules  
- [metadata-vs-decision-layer.md](./metadata-vs-decision-layer.md) — Layer 1 vs Layer 2  
- [minimum-normalized-policy-schema.md](./minimum-normalized-policy-schema.md) — canonical comparison readiness (schema)  
