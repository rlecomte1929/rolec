# Company Scope Guardrails

**Date:** 2025-03-19  
**Purpose:** Document backend enforcement of company-scoped access for HR users. Frontend filtering alone is insufficient; data access must be enforced at the API/database level.

---

## What Was Previously Unsafe or Ambiguous

### 1. HR company resolution inconsistency

| Flow | Previously | Issue |
|------|------------|-------|
| **assign_case** | `profile.get("company_id")` | Ignored `hr_users.company_id`; could differ from list |
| **create_case (HR)** | `profile.get("company_id")` | Same as above |
| **list_hr_assignments** | `_get_hr_company_id(effective)` | hr_users first, then profile |

**Impact:** HR with `hr_users.company_id` set but `profiles.company_id` null could list assignments (via fallback to list_assignments_for_hr) but could not create cases or assign.

### 2. No company validation on assign

When `hr_company_id` was null, assign_case continued with `None` and could create assignments without company linkage on the case.

### 3. Claim flow

Claim flow validates `employee_identifier` match only. No explicit company check. This is acceptable because:
- Only the person with matching email/username can claim
- Assignment was created for that identifier by HR
- Cross-company claim would require same identifier across companies (rare, and identifier is the intended binding)

---

## Checks Now in Place

### 1. Unified HR company resolution

**create_case** and **assign_case** now use `_get_hr_company_id(effective)` (same as list_hr_assignments):
- `db.get_hr_company_id(profile_id)` → hr_users.company_id
- Fallback: profile.company_id

### 2. Company required for HR case/assign

| Endpoint | Check |
|----------|-------|
| `POST /api/hr/cases` | `company_id = _get_hr_company_id(effective)`; if null → 400 "No company linked to your profile. Please complete your company profile first." |
| `POST /api/hr/cases/{case_id}/assign` | Same check; case is upserted with company_id when missing |

### 3. List assignments (HR)

| User Type | Query | Company Scope |
|-----------|-------|---------------|
| Admin (no impersonation) | `list_all_assignments()` | All assignments |
| HR with company_id | `list_assignments_for_company(company_id)` | `rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid)` |
| HR without company_id | `list_assignments_for_hr(hr_user_id)` | Assignments where hr_user_id = current user (owner-only fallback) |

### 4. Get assignment detail (HR)

`GET /api/hr/assignments/{assignment_id}` uses `_hr_can_access_assignment`:
- Admin: always allowed
- HR: assignment owner (hr_user_id) or `assignment_belongs_to_company(assignment_id, hr_company_id)`

### 5. Assignment visibility (shared)

`_require_assignment_visibility` is used by timeline, services, questions, etc.:
- Employee: must be `employee_user_id` on assignment
- HR: admin, owner, or company match via `assignment_belongs_to_company`

---

## Endpoints Protected and How

| Endpoint | Auth | Company/Scope Check |
|----------|------|---------------------|
| `GET /api/hr/assignments` | HR | list_assignments_for_company or list_assignments_for_hr |
| `GET /api/hr/assignments/{id}` | HR | _hr_can_access_assignment |
| `POST /api/hr/cases` | HR | _get_hr_company_id required |
| `POST /api/hr/cases/{id}/assign` | HR | _get_hr_company_id required; case upserted with company |
| `POST /api/employee/assignments/{id}/claim` | Employee | employee_identifier match (identity binding) |
| `GET /api/assignments/{id}/timeline` | HR or Employee | _require_assignment_visibility |
| `GET /api/services/context` | HR or Employee | _require_assignment_visibility |
| Admin assignment endpoints | Admin | Admin-only; company_id from request body |

---

## Database-Level Scoping

- `list_assignments_for_company` joins case_assignments → relocation_cases and hr_users; filters by company_id
- `assignment_belongs_to_company` uses same predicate: `(rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))`
- Row-level security (RLS): if Supabase/PostgREST is used for direct access, separate RLS policies may apply; this document covers the FastAPI backend.

---

## References

- `backend/main.py`: assign_case, create_case, list_hr_assignments, _get_hr_company_id, _hr_can_access_assignment, _require_assignment_visibility
- `backend/database.py`: list_assignments_for_company, assignment_belongs_to_company, get_hr_company_id
