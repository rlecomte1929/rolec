# HR Employee Data Reconciliation

**Date:** 2025-03-19  
**Purpose:** Categories of inconsistent employee data and remediation.

---

## Categories of Inconsistent Data

| Category | Description | Remediation |
|----------|-------------|-------------|
| **Profiles without employees** | `profiles` has `role IN ('EMPLOYEE','EMPLOYEE_USER')` and `company_id` but no `employees` row | `ensure_employees_for_company` backfills on list |
| **HR-assigned without employees** | `assign_case` created/updated profile but never created `employees` row | `ensure_employee_for_profile` added to `assign_case` |
| **Admin-created employees** | Admin flow already calls `ensure_employee_for_profile` | No change needed |
| **Duplicate employees** | Same profile with multiple `employees` rows (different companies) | `ensure_employee_for_profile` updates existing row's `company_id`; one row per profile |
| **Orphaned employees** | `employees` row with invalid `profile_id` or `company_id` | Not addressed; low risk for list correctness |

---

## Remediation Plan

1. **Automatic on list:** `ensure_employees_for_company(company_id)` runs before every HR employee list. This backfills missing `employees` rows from `profiles`.

2. **Automatic on assign:** `ensure_employee_for_profile(profile_id, company_id)` runs in `assign_case` when an employee user is linked. New assignments create the `employees` row immediately.

3. **Manual review:** If duplicate or orphaned records are found, manual cleanup may be needed. No automated deduplication beyond the existing upsert logic in `ensure_employee_for_profile`.

---

## What Can Be Fixed Automatically

- Missing `employees` rows for profiles with `role` EMPLOYEE/EMPLOYEE_USER and `company_id` — fixed by `ensure_employees_for_company`.
- New assignments not creating `employees` — fixed by `ensure_employee_for_profile` in `assign_case`.

---

## What Needs Manual Review

- Duplicate `employees` rows for the same profile across companies (unusual; ensure_* updates company_id).
- Orphaned `employees` rows (profile deleted but employee row remains).
- Profiles with wrong `role` or `company_id` from legacy flows.
