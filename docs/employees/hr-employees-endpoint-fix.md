# HR Employees Endpoint Fix

**Date:** 2025-03-19  
**Issue:** `GET /api/hr/employees` returns 400 Bad Request for valid HR users.

---

## Root Cause

In `list_hr_company_employees`:

```python
company_id = _get_hr_company_id(effective)
if not company_id:
    raise HTTPException(status_code=400, detail="No company linked to your profile")
```

When `_get_hr_company_id` returns `None` (no `hr_users.company_id`, no `profile.company_id`), the endpoint raised 400.

`get_company_profile` uses the same resolution but returns 200 with `company: null` when no company. The Employees endpoint was inconsistent and caused the frontend to show "Unable to load employees" before any list was attempted.

---

## Fix Applied

1. **Return 200 with empty list instead of 400** when `company_id` is None.
   - Aligns with `get_company_profile` behavior.
   - Response: `{"employees": [], "has_company": false}`.

2. **Reconcile profiles into employees** before listing:
   - Call `db.ensure_employees_for_company(company_id)` (same as Admin).
   - Backfills `employees` from `profiles` with `role IN ('EMPLOYEE','EMPLOYEE_USER')` and `company_id`.
   - Ensures Admin- and HR-assignment-created profiles appear in the list.

3. **Create employees row on assignment** in `assign_case`:
   - Call `db.ensure_employee_for_profile(employee_user["id"], hr_company_id)` when HR assigns a case to an employee.
   - Ensures newly assigned employees appear in the HR Employees tab.

4. **Add `has_company` flag** in the response so the frontend can distinguish:
   - `has_company: false` — HR has no company; prompt to complete company profile.
   - `has_company: true`, `employees: []` — Company exists but has no employees.

---

## Contract

| Scenario | Status | Response |
|----------|--------|----------|
| No company linked | 200 | `{"employees": [], "has_company": false}` |
| Company, no employees | 200 | `{"employees": [], "has_company": true}` |
| Company with employees | 200 | `{"employees": [...], "has_company": true}` |
| Unauthorized | 401 | error |
| Server error | 500 | error |

---

## Guardrails

- HR sees only employees for `_get_hr_company_id` (hr_users or profile fallback).
- `list_employees_with_profiles` filters by `company_id`.
- No frontend-only filtering; backend enforces company scope.
