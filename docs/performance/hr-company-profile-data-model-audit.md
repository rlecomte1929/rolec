# HR Company Profile — Data Model Audit

**Date:** 2025-03-17  
**Purpose:** Verify Admin→Company→HR relationships and canonical company resolution path.

---

## Schema Overview

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| **companies** | id, name, country, size_band, address, phone, hr_contact, ... | Company profile record (created by Admin or on first HR save) |
| **profiles** | id, role, email, full_name, **company_id**, created_at | User identity; company_id may be set by Admin assign |
| **hr_users** | id, **company_id**, **profile_id**, permissions_json | Canonical HR→company mapping (one row per HR user) |
| **employees** | id, **company_id**, **profile_id**, band, ... | Employee→company mapping |
| **relocation_cases** | id, hr_user_id, employee_id, **company_id**, ... | Case linked to company |
| **case_assignments** | id, case_id, hr_user_id, employee_user_id, ... | Assignment; company via case or hr_users |

---

## Canonical Path: HR User’s company_id

**Preferred source:** `hr_users.company_id` (via `profile_id`)

```
HR user_id (profile_id) → hr_users WHERE profile_id = ? → company_id
```

**Fallback:** `profiles.company_id` if no `hr_users` row exists

**Implementation:** `db.get_hr_company_id(profile_id)` in `database.py`:
1. `SELECT company_id FROM hr_users WHERE profile_id = :pid LIMIT 1`
2. If missing: `get_profile_record(pid)` → `profile.company_id`

---

## Admin → Company → HR Flow

1. **Admin creates company:** `POST /api/admin/companies` → `db.create_company()` → `companies` row with id, name, country, etc.
2. **Admin assigns HR to company:** `POST /api/admin/people/{person_id}/assign-company`:
   - `db.set_profile_company(person_id, company_id)` — updates `profiles.company_id`, `hr_users.company_id`, `employees.company_id`
   - `db.ensure_hr_user_for_profile(person_id, company_id)` — creates `hr_users` row if missing

**Result:** HR user has `hr_users.profile_id` → `hr_users.company_id` and `profiles.company_id` in sync.

---

## Company Profile Record Existence

**Question:** Is a company profile record guaranteed when HR opens Company Profile?

**Current behavior:**
- Admin creates company → `companies` row exists with basic fields (name, country, etc.)
- HR assigned to company → `hr_users` and `profiles` point to that `company_id`
- When HR opens Company Profile, `get_company_profile`:
  - Resolves `company_id` via `_get_hr_company_id`
  - Fetches `db.get_company(cid)` or `db.get_company_for_user(effective["id"])` as fallback

**Gap:** If Admin creates company but never assigns the HR user to it (or assignment fails), `get_hr_company_id` can return `None`. Then `get_company_for_user` uses `profiles.company_id`, which may also be null. In that case, `company` is `None` and the frontend shows an empty form.

**Preferred model:** Admin always assigns HR to company. When that’s done, `hr_users` has the link and company resolution is reliable.

---

## Employees and Assignments: Company Scope

**Employees:** `employees.company_id` — scoped by company.  
`list_employees_with_profiles(company_id)` filters by `employees.company_id`.

**Assignments:** Company comes from:
- `relocation_cases.company_id`, or
- `hr_users.company_id` when `relocation_cases.company_id` is null

`list_assignments_for_company(company_id)` uses:
```sql
WHERE (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
```

So assignments are company-scoped via case or HR ownership.

---

## Redundancy and Inefficiency

1. **Two company resolution paths**
   - `get_company_for_user` uses only `profiles.company_id`
   - `get_hr_company_id` uses `hr_users` first, then `profiles`
   - For HR, `hr_users` is canonical; `get_company_for_user` can be wrong if `profiles.company_id` is stale or empty.

2. **Company-profile endpoint uses two fallbacks**
   - `get_company_profile`: `cid = _get_hr_company_id(effective)` then `company = db.get_company(cid) if cid else db.get_company_for_user(effective["id"])`
   - Two different resolution paths in one endpoint.

3. **`/api/company` vs `/api/hr/company-profile`**
   - `/api/company`: `get_company_for_user(user["id"])` — profile-based
   - `/api/hr/company-profile`: HR-specific path with `_get_hr_company_id`
   - For HR, `/api/company` may return nothing while `/api/hr/company-profile` works.

4. **Repeated company_id resolution**
   - Each endpoint independently calls `_get_hr_company_id` or `get_company_for_user`.
   - No shared “HR company context” — each request recomputes.

---

## Business Expectation vs Implementation

| Expectation | Implementation |
|-------------|----------------|
| Company created by Admin | ✅ `POST /api/admin/companies` |
| Company assigned to HR | ✅ `assign_person_company` → `hr_users` + `profiles` |
| HR opens Company Profile with known company | ✅ `_get_hr_company_id` resolves it |
| Company profile prefilled | ⚠️ Depends on Admin: create_company has name, country, etc. Assign flow does not prefill more fields |
| Employees/assignments linked to company | ✅ Scoped by `company_id` |
| Single canonical context | ❌ No shared context; each call resolves again |

---

## Recommendations

1. **Unify HR company resolution:** Use `_get_hr_company_id` consistently for HR; avoid `get_company_for_user` for HR.
2. **Introduce shared HR company context:** Resolve `company_id` once per session/page and reuse (e.g. `useHrCompanyContext`).
3. **Optimize `/api/hr/company-profile`:** Single query joining `hr_users` → `companies` to reduce round-trips.
4. **Ensure company exists on Admin assign:** When Admin assigns HR to company, ensure the `companies` row exists and is populated.
5. **Fix `/api/company` for HR:** For HR users, resolve via `get_hr_company_id` instead of `get_company_for_user` so header branding matches company-profile.
