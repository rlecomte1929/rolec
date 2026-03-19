# HR Employees Tab — Results and Verification

**Date:** 2025-03-19  
**Summary:** Root cause fixed, canonical employee list aligned, empty state corrected.

---

## Root Cause of 400

`GET /api/hr/employees` returned 400 when `_get_hr_company_id(effective)` was `None`:
- No `hr_users.company_id`
- No `profile.company_id`

The endpoint raised `HTTPException(400, "No company linked to your profile")` instead of returning an empty list, which caused the frontend to show "Unable to load employees" and then "No employees found" after error handling.

---

## What Changed in the Endpoint

1. **400 → 200 with empty list** when `company_id` is None.
2. **Reconciliation before list:** `db.ensure_employees_for_company(company_id)` so profiles with EMPLOYEE role and `company_id` are backfilled into `employees`.
3. **Response shape:** Added `has_company: boolean` so the frontend can distinguish "no company" from "company has no employees".
4. **assign_case:** Added `db.ensure_employee_for_profile(employee_user["id"], hr_company_id)` when HR assigns a case to an employee.

---

## What Changed in Data Model / Reconciliation

- HR list now uses the same backfill as Admin: `ensure_employees_for_company`.
- HR assignment flow now creates `employees` rows via `ensure_employee_for_profile`.
- Canonical source: `employees` table filtered by `company_id`; backfilled from `profiles` when missing.

---

## Before/After Request Behavior

| Metric | Before | After |
|--------|--------|-------|
| 400 on no company | Yes | No; returns 200 + `[]` |
| Employees from Admin setup | Visible (Admin only) | Visible to HR (backfill) |
| Employees from HR assignment | Missing | Visible (ensure on assign) |
| Empty state | "No employees" (could follow 400) | Separate "Complete company profile" vs "No employees" |

---

## Before/After Page Loading

- **Before:** Request 400 → error → sometimes "No employees" as fallback.
- **After:** Request 200 → list or empty; `has_company` drives empty-state copy.

---

## Manual Verification Checklist

- [ ] Valid HR with company can load Employees page without 400.
- [ ] Only own company employees appear.
- [ ] Employees created via Admin appear in HR Employees tab.
- [ ] Employees created via HR assignment flow appear in HR Employees tab.
- [ ] HR without company sees "Complete your company profile" and link to company profile.
- [ ] HR with company but no employees sees "No employees found for your company".
- [ ] Page loads without unnecessary fan-out or full-detail fetches per row.
- [ ] Error state ("Unable to load employees") appears only on real fetch failure, not on 400.

---

## Remaining Follow-ups

- Optional: server-side search (name/email) with debounce.
- Optional: pagination if employee count grows.
- Optional: instrumentation (request duration, payload size) for monitoring.
