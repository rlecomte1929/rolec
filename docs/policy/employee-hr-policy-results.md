# Employee HR Policy — results & verification

## Summary

| Area | Change |
|------|--------|
| **API** | New **`GET /api/employee/me/assignment-package-policy`**: one response with `status`: `found` \| `no_policy_found` \| `no_assignment` \| `error`. |
| **Resolver** | **Fast path** when no published policy exists for any candidate company (no full rule engine). |
| **Cache** | If stored `resolved_assignment_policies.policy_version_id` matches current published version, return DB benefits without recomputing. |
| **Read-only GETs** | Employee policy GETs use **`read_only=True`**: no `create_case` / `upsert_relocation_case` / `ensure_profile_record` on policy load. |
| **UI** | Single fetch in `EmployeePolicyContent`; **neutral** card for `no_policy_found` with **exact** product copy from the API. |
| **Display logic** | Policy **header** shows when a published policy is linked even if **benefit list is empty** (with explanatory line). |

## Response shape (combined endpoint)

- **`found`:** `has_policy: true`, `policy`, `benefits`, `exclusions`, `resolution_context`, `resolved_at`.  
- **`no_policy_found`:** `has_policy: false`, `message` + `message_secondary` (canonical fallback).  
- **`no_assignment`:** static assignment message.  
- **`error`:** true failure only; distinct from `no_policy_found`.

## Requests removed from initial load

- **Removed from critical path:** separate **`/api/employee/assignments/current`** + **`/api/employee/assignments/{id}/policy`** sequence for this page (replaced by one call).  
- **Note:** The combined endpoint still runs the same **reconcile** helper as `assignments/current` once per load (intentional parity).

## Before / after (qualitative)

| Metric | Before | After |
|--------|--------|--------|
| Round-trips (employee policy page) | 2 | 1 |
| No published policy | Full resolver attempt + mutations | Early exit after published check |
| Repeat visits (same published version) | Full rule resolution | Often **DB cache hit** |

## Backend performance notes

- **Indexes:** ensure indexes on `resolved_assignment_policies(assignment_id)`, `policy_versions(company_id, status)`, and company policy FKs as already in migrations; add more only if traces show slow `get_company_policy_with_published_version`.  
- **Payload:** employee responses include only summary policy fields + benefit rows (no workspace editor graph).

## Manual verification checklist

- [ ] Employee **with** published workspace policy for their company chain sees policy **quickly** after one request.  
- [ ] Employee **without** any published policy for candidate companies sees **`no_policy_found`** with the **exact** two sentences (primary + secondary).  
- [ ] **`no_policy_found`** is **not** a 500 and **not** the same UI as **`error`**.  
- [ ] Published policy with **zero matching benefit rules** still shows **policy title/metadata** + empty-state explanation (not the global “no policy published” message).  
- [ ] HR **draft** policy does **not** appear until **published**.  
- [ ] **Assignment scoping:** another employee’s assignment id cannot be used to read policy (existing `_require_assignment_visibility` on per-assignment routes).  
- [ ] Network tab on employee policy page: **one** `assignment-package-policy` call on entry (no duplicate policy GET from this screen).

## Follow-ups (optional)

- Add **ETag** or short **Cache-Control** for `assignment-package-policy` if needed.  
- Consider **React Query** with a stable key to avoid duplicate in-flight calls if the route remounts.  
- Align or deprecate **`/api/employee/policy/applicable`** if product wants a single policy story everywhere.
