# HR Employee Scope Guardrails

**Date:** 2025-03-19  
**Purpose:** Document backend enforcement of company-scoped access for HR users.

---

## Rules

1. **HR user can list only employees from their company**
   - `list_hr_company_employees` resolves `company_id` via `_get_hr_company_id`.
   - `db.list_employees_with_profiles(company_id)` filters by `e.company_id = :cid`.

2. **HR user cannot fetch employee detail from another company**
   - `get_hr_company_employee` uses `db.get_employee_for_company(employee_id, company_id)`.
   - Returns 404 if employee is not in company.

3. **HR user cannot update employees outside their company**
   - `update_hr_company_employee` uses `db.update_employee_limited(employee_id, company_id, ...)`.
   - Returns 404 if employee is not in company.

4. **Employee search/filter is limited to HR's company**
   - Current list endpoint returns all company employees; no cross-company leakage.
   - Future search params must be applied after company scope.

5. **Admin access remains broader**
   - Admin endpoints (e.g. `list_employees` for Admin) use company_id from request/context.
   - Admin is not restricted to a single company when querying across companies.

---

## Implementation

| Endpoint | Company Resolution | Query Scope |
|----------|--------------------|-------------|
| `GET /api/hr/employees` | `_get_hr_company_id(effective)` | `list_employees_with_profiles(company_id)` |
| `GET /api/hr/employees/{id}` | `_get_hr_company_id(effective)` | `get_employee_for_company(id, company_id)` |
| `PATCH /api/hr/employees/{id}` | `_get_hr_company_id(effective)` | `update_employee_limited(id, company_id, ...)` |

---

## No Frontend Filtering

Security is enforced in the backend. Frontend must not be trusted to filter employees. All HR employee endpoints derive company from the authenticated user.
