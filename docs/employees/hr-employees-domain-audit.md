# HR Employees Domain Audit

**Date:** 2025-03-19  
**Purpose:** Document the employee/company data model and identify causes of the Employees tab 400 and missing employee visibility.

---

## Canonical Entities and Relationships

| Entity | Table | Key Columns | Purpose |
|--------|-------|-------------|---------|
| **companies** | `companies` | id, name, country | Company record |
| **hr_users** | `hr_users` | id, company_id, profile_id | HR→company mapping |
| **profiles** | `profiles` | id, role, email, full_name, company_id | User identity |
| **employees** | `employees` | id, company_id, profile_id, band, status | Employee→company mapping |
| **case_assignments** | `case_assignments` | id, employee_user_id, employee_identifier, hr_user_id | Assignment to employee |

---

## Employee-to-Company Linkage

- **Canonical:** `employees.company_id` — employee belongs to company
- **Secondary:** `profiles.company_id` — user’s company (may exist without employees row)
- **Indirect:** `case_assignments` links case to `employee_identifier` or `employee_user_id` (profile id)

---

## HR Company Resolution

`_get_hr_company_id(effective)`:
1. `db.get_hr_company_id(uid)` → `hr_users.company_id`
2. Fallback: `profile.company_id` from profiles

When both are null → 400 "No company linked to your profile" on `/api/hr/employees`.

---

## Admin vs HR Employee Creation

| Flow | Creates employees row? | Creates profile? |
|------|------------------------|------------------|
| **Admin assign-company** | `ensure_employee_for_profile` | Yes (set_profile_company) |
| **Admin create person (EMPLOYEE)** | `ensure_employee_for_profile` | Yes |
| **Admin set role to EMPLOYEE** | `ensure_employee_for_profile` | Yes |
| **HR assign_case** (existing user) | No | `ensure_profile_record` only |
| **HR assign_case** (auto-create user) | No | `ensure_profile_record` only |

Result: HR-created assignments update `profiles` with `company_id` but do not create `employees` rows. HR Employees list uses `list_employees_with_profiles(company_id)` → only `employees` table. So HR-assigned employees are missing from the list.

---

## Admin List vs HR List

| Endpoint | Before list | Source |
|----------|-------------|--------|
| **Admin** `list_employees` | `ensure_employees_for_company(company_id)` | Backfills from profiles |
| **HR** `list_hr_company_employees` | None | `list_employees_with_profiles` only |

Admin sees employees because of the backfill; HR does not.

---

## Root Cause of 400

- 400 when `_get_hr_company_id(effective)` is None.
- Happens when HR has no `hr_users` row and `profile.company_id` is null.
- `get_company_profile` can still return 200 with `company: null` in that case.

---

## Likely Causes of Missing Employees

1. **No employees row:** HR `assign_case` sets profile but never calls `ensure_employee_for_profile`.
2. **No backfill:** HR list does not call `ensure_employees_for_company`.
3. **400 before list:** If company_id is null, we never reach the list logic.

---

## Recommendations

1. Use `get_company_for_user` fallback and return `[]` when no company instead of 400.
2. Call `ensure_employees_for_company` before HR list (same as Admin).
3. In `assign_case`, call `ensure_employee_for_profile` when linking an existing employee user.
4. Optionally include assignments-derived employees in the HR list if needed.
