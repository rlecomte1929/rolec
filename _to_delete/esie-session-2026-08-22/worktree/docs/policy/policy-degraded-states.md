# Policy degraded states (HR workspace + employee surfaces)

This document lists **explicit** states when policy data is missing, incomplete, or not yet comparison-ready. UI should stay usable (no indefinite vague loaders) and name the situation in one glance.

Related: [comparison-readiness-and-fallback.md](./comparison-readiness-and-fallback.md), [published-policy-consumption-rules.md](./published-policy-consumption-rules.md), [services-page-policy-consumption.md](./services-page-policy-consumption.md), [policy-performance-hardening.md](./policy-performance-hardening.md) (latency/payload optimizations for these states), [hr-to-employee-policy-verification.md](./hr-to-employee-policy-verification.md) (QA matrix + analytics events).

---

## HR Policy workspace (HR-facing)

Derived in code by `deriveHrPolicyPipelineState` (`frontend/src/features/policy/hrPolicyDegradedState.ts`) and surfaced via `HrPolicyPipelineBanner` on the HR policy review workspace. Copy lives in `HR_POLICY_PIPELINE_COPY`.

| State | Meaning | Typical UI behavior |
|-------|---------|---------------------|
| **`workspace_empty`** | No primary document, no draft normalized snapshot, no published version in the normalized payload. | Neutral banner: prompt to upload or ensure a company policy exists. Workspace remains navigable. |
| **`uploaded_not_normalized`** | Latest document is not in a normalized/approved stage, or extraction/classification still in progress. | Info banner: normalization not complete; clarify that Layer‑1 doc metadata is not employee-facing until a published version exists. |
| **`normalized_failed`** | Document `processing_status === 'failed'` (optional `extraction_error` snippet). | Error banner; show short error detail when present; Reprocess path. |
| **`normalized_partial`** | Draft version has some structure (e.g. benefit rules or exclusions) **or** document marked normalized/approved but empty structure — **and** no published version yet. | Warning banner: review matrix and **Publish version**; employees do not see this until published. |
| **`published_not_comparison_ready`** | Published version exists; `published_comparison_readiness.comparison_ready === false`. | Warning banner; optional first comparison blockers in subtext; employees get summary-style / partial employee UX (see below). |
| **`published_comparison_ready`** | Published + `comparison_ready === true`. | Success banner; employees with matching resolution can use comparison where product allows. |

### HR: what blocks employee **comparison** vs **summary**

| HR state | Employee sees a matching published policy? | Employee **comparison** (bars, gated comparisons, eligibility-style badges) | Employee **summary / “on file”** style messaging |
|----------|---------------------------------------------|-------------------------------------------------------------------------------|-----------------------------------------------------|
| `workspace_empty` | No | N/A (no published policy for context) | N/A at policy level |
| `uploaded_not_normalized` | No | Blocked | N/A |
| `normalized_failed` | No | Blocked | N/A |
| `normalized_partial` | No | Blocked | N/A |
| `published_not_comparison_ready` | Yes (if resolution matches) | **Blocked** (`comparison_available === false`) | **Allowed** — partial policy messaging; costs still reviewable without comparison |
| `published_comparison_ready` | Yes (if resolution matches) | **Allowed** when APIs return `comparison_available === true` | Full comparison + badges where implemented |

---

## Employee HR Policy / Services (employee-facing)

These are **product** states inferred from resolution + API flags (`has_policy`, `comparison_available`, `comparison_readiness`, services `services-policy-context`). Copy is centralized in `frontend/src/features/policy/employeePolicyMessages.ts` and used in views such as `EmployeeResolvedPolicyView`, package summary, and HR Policy employee tab.

| State | Condition (conceptual) | UI behavior |
|-------|------------------------|-------------|
| **No matching published policy** | Resolution finds no published company policy for the assignment context; or employee has no assignment / wrong company context. | Explicit “not published yet” messaging (`EMPLOYEE_HR_POLICY_WAIT_*`); **no** spinner that implies a policy is loading forever. Short loading only while assignment/policy fetch is in flight (`EMPLOYEE_POLICY_LOADING_ASSIGNMENT`). |
| **Policy exists but not comparison-ready** | Published policy resolves; `comparison_available === false` (readiness gate failed). | Amber / notice: comparison unavailable primary + secondary (`EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_*`); optional “partial policy information” card (`EMPLOYEE_POLICY_PARTIAL_INFO_*`). **No** comparison bars or gated comparison UI; **no** eligibility-style badges that depend on comparison. |
| **Policy comparison available** | `comparison_available === true` (and resolution succeeded). | Positive strip (`EMPLOYEE_POLICY_COMPARISON_ACTIVE_*`); show comparison bars, caps, and badges where the screen implements them. |
| **Partial policy info available** | Same as “not comparison-ready” from the employee lens: policy **on file** but structured cards / comparison withheld. | Treat as **summary-only** mode: explain that HR can complete rules; user can still use Services costs without policy comparison. |

### Employee: comparison vs summary-only

| Employee state | Blocks comparison UI? | Allows summary / costs-only behavior? |
|----------------|----------------------|----------------------------------------|
| No matching published policy | Yes (nothing to compare) | Yes — Services and other pages load with explicit empty/missing-policy copy |
| Policy exists, not comparison-ready | **Yes** | **Yes** — summary notices + partial info; service pricing still usable |
| Policy comparison available | No | Yes — full policy-backed comparison where built |
| Partial policy info (wording) | Yes (same gate as not comparison-ready) | Yes |

---

## Implementation map

| Area | Location |
|------|----------|
| HR pipeline derivation | `frontend/src/features/policy/hrPolicyDegradedState.ts` |
| HR banner | `frontend/src/features/policy/HrPolicyPipelineBanner.tsx` |
| Employee messages | `frontend/src/features/policy/employeePolicyMessages.ts` |
| Normalized payload (includes `published_version`, `published_comparison_readiness`) | `GET /api/company-policies/{policy_id}/normalized` (`backend/main.py`) |
| Readiness evaluation | `backend/services/policy_comparison_readiness.py` |
