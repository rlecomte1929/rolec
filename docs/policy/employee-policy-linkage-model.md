# Employee applicable policy — linkage model

## Canonical source of truth

1. **Published company policy (workspace)**  
   - Stored per **company** with **policy** + **policy_versions** rows.  
   - Only versions in a **published** state are considered for employees (`db.get_company_policy_with_published_version`).

2. **Assignment → company candidates (precedence)**  
   Implemented in `collect_company_id_candidates_for_assignment` (`backend/services/policy_resolution.py`), in order:

   | Priority | Source | Field / logic |
   |----------|--------|----------------|
   | 1 | Relocation case | `relocation_cases.company_id` |
   | 2 | HR owner | `assignment.hr_user_id` or `case.hr_user_id` → `hr_users` / HR profile → **company_id** |
   | 3 | Employee profile | `profiles.company_id` for `assignment.employee_user_id` |

3. **Winner selection**  
   Walk candidates **in order**; use the **first** company that has a **published** policy version.  
   This is **deterministic** and does not depend on frontend heuristics.

4. **Materialized package for the assignment**  
   - Table: **`resolved_assignment_policies`** (+ benefit/exclusion child tables).  
   - Built by `resolve_policy_for_assignment` from the **published version’s** benefit rules, applicability, conditions, exclusions, tier overrides.  
   - **Draft / unpublished** workspace content is never read for employee resolution.

5. **Employee read path**  
   - **`GET /api/employee/me/assignment-package-policy`** (preferred for the employee UI).  
   - **`GET /api/employee/assignments/{id}/policy`** (assignment-scoped; same resolver, `read_only=True`).

## HR publication alignment

- Until HR **publishes** a version for a company that matches the candidate list, the API returns **`no_policy_found`** (valid state, not an error).  
- After publication, the same path returns **`found`** with policy metadata + resolved benefits (possibly empty if no rules match the employee’s resolution context).

## Disconnected / legacy path (not used for this page)

- **`GET /api/employee/policy/applicable`** uses `get_published_hr_policy_for_employee` / band–destination heuristics — a **different** lineage from the **company policy workspace** used by HR Policy v2.  
- The **Assignment Package & Limits** page is intentionally wired to **workspace published policy + resolved_assignment_policies**, not that legacy resolver.

## Where the old implementation was ambiguous

- **Chained fetches** made it unclear that **one** assignment id drives everything.  
- **Mutations on GET** (case/profile back-fill) blurred read vs write and added latency.  
- **Frontend required benefits.length > 0**, conflating “no published policy” with “policy resolved to zero rows”.

## Resolution context (rule matching)

From `extract_resolution_context`: assignment type, family status, destination hints, duration, tier/band, dependents — used only **after** a published version is chosen, to filter benefit rules. It does **not** change which **company** or **published version** wins; that is purely candidate order + first published hit.
