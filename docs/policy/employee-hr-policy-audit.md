# Employee HR Policy page — request & resolution audit

## Route & UI

- **Path:** `/hr/policy` (employee role; `/employee/hr-policy` redirects here).
- **Component:** `frontend/src/pages/HrPolicy.tsx` → `EmployeePolicyContent`.
- **Display:** `frontend/src/features/policy/EmployeeResolvedPolicyView.tsx`.

## Previous behavior (before this pass)

### Request sequence on page entry

1. **`GET /api/employee/assignments/current`** (via `employeeAPI.getCurrentAssignment`, **30s client cache**).
2. After `assignment.id` was known: **`GET /api/employee/assignments/{id}/policy`**.

### Issues

| Issue | Impact |
|-------|--------|
| **Two round-trips** on cold cache | Perceived lag; policy waited on assignment finishing first. |
| **Heavy resolution on every policy GET** | `_resolve_published_policy_for_employee` could run full `resolve_policy_for_assignment` (many queries) and **mutate** case/profile on read (`create_case`, `upsert_relocation_case`, `ensure_profile_record`). |
| **No fast “no published policy” path** | Even when no company had a published version, work ran until `resolve_policy_for_assignment` returned `None`. |
| **Strict UI gate** | `EmployeeResolvedPolicyView` required `benefits.length > 0` to treat as “has policy”, so a **valid linked policy with zero resolved benefit rows** showed the same empty state as “no policy”. |

### Unrelated requests

The HR Policy **employee** branch did **not** mount timeline, sufficiency, or services context. Slowness was dominated by **assignment + policy** and backend resolution work, not those modules.

---

## Current behavior (after this pass)

### Request sequence on page entry

1. **`GET /api/employee/me/assignment-package-policy`**  
   - Resolves **current assignment** (same reconcile hook as `/assignments/current`, single pass).  
   - Runs **read-only** policy resolution (`read_only=True`: no case creation / profile back-fill on this path).  
   - **Fast reject:** if no company candidate has a **published** policy version → immediate `status: no_policy_found` with canonical copy.  
   - **Cache hit:** if `resolved_assignment_policies.policy_version_id` matches the **current published** version → return benefits/exclusions from DB without recomputing rules.

Legacy **`GET /api/employee/assignments/{id}/policy`** remains for other callers; it now uses **`read_only=True`** as well.

### Critical vs non-critical

| Request | Critical for first paint |
|---------|---------------------------|
| `assignment-package-policy` | Yes (single call) |
| Separate `assignments/current` + `.../policy` | No longer used on this page |

---

## Likely causes of policy “not found” (historical)

1. **No `company_id`** on case and missing HR/profile company linkage → empty candidate list.  
2. **No published policy version** for any candidate company (`get_company_policy_with_published_version`).  
3. **Resolved row stale** after HR publishes a new version (mitigated by version-id check + recompute).  
4. **UI bug:** policy present but **zero benefits** after rule filtering → old UI showed “no policy”.

---

## Files touched

- `backend/main.py` — `_resolve_published_policy_for_employee`, new `GET /api/employee/me/assignment-package-policy`, constants for fallback copy.  
- `backend/services/policy_resolution.py` — shared candidate + published-policy helpers; safe `case` access in `extract_resolution_context`.  
- `frontend/src/pages/HrPolicy.tsx` — `EmployeePolicyContent` uses combined API.  
- `frontend/src/features/policy/EmployeeResolvedPolicyView.tsx` — `resolvedSnapshot`, correct `hasPolicy`, empty-benefits copy.  
- `frontend/src/api/client.ts` — `getMyAssignmentPackagePolicy`.
