# Company linkage audit (Admin ↔ HR)

**Date:** 2025-03-20  
**Issue:** HR `/hr/company-profile` showed an empty form while Admin had already created a company and assigned the HR user.

---

## Canonical source of truth

| Field | Storage |
|-------|---------|
| Company name, legal name, country, HQ city, size band, address, phone, HR contact, logo, industry, defaults, status, plan, seat limits | Single table **`companies`** (row keyed by `id` / `company_id`) |
| Which company an HR user belongs to | **`profiles.company_id`** (FK-style reference to `companies.id`) |
| HR seat / permissions row | **`hr_users`** (`profile_id` → profiles.id, `company_id` → companies.id) |

There is **no** separate `company_profile` table. Admin and HR both read/write the same **`companies`** row via `db.create_company` (upsert) and `db.get_company`.

---

## Admin flow

- **Create:** `POST /api/admin/companies` → `db.create_company(...)` → new UUID in `companies`.
- **Assign HR to company:** `POST /api/admin/people/{person_id}/assign-company` → `db.set_profile_company(person_id, company_id)` which:
  - `UPDATE profiles SET company_id = ...`
  - `UPDATE hr_users SET company_id = ... WHERE profile_id = ...`
  - `UPDATE employees SET company_id = ... WHERE profile_id = ...`
- For role HR, also `ensure_hr_user_for_profile(person_id, company_id)` so an `hr_users` row exists.

---

## HR flow

- **Load:** `GET /api/hr/company-profile` → resolve `company_id` → `db.get_company(company_id)`.
- **Save:** `POST /api/hr/company-profile` → resolve/create `company_id` on profile → `db.create_company(...)` (upsert same row).

---

## How HR company context was resolved (before fix)

1. `db.get_hr_company_id(profile_id)` read `hr_users.company_id`.
2. **Bug:** If an `hr_users` row **existed** but `company_id` was **NULL**, the function returned `None` and **did not** fall back to `profiles.company_id`.
3. Admin assignment correctly set `profiles.company_id`, but if `hr_users` predated the assignment or was created with a null `company_id`, resolution failed.
4. Fallback `get_company_for_user` uses only `profiles.company_id` — but `get_company_profile` called `get_company(cid)` when `cid` was truthy from a **buggy** path; the main failure was `cid` being wrong/empty when `hr_users` masked the profile.

**Net effect:** HR could have `profiles.company_id` pointing at the Admin-created company while `get_hr_company_id` returned `None`, yielding `company: null` and an empty form.

---

## Duplicate / disconnected records

- **Risk:** HR “first save” without prior `company_id` generates a **new** UUID and a second `companies` row (orphan from Admin’s company). Mitigation: always prefer existing `profile.company_id` / `_get_hr_company_id` before minting a new id (existing `save_company_profile` logic).
- **Risk:** Multiple `hr_users` rows per `profile_id` is not prevented by DB constraint; code uses `LIMIT 1` (should stay rare).

---

## Recommendation (canonical model)

- **Single `companies` row per organization** (already the model).
- **`profiles.company_id`** is the primary link for “this user belongs to this company.”
- **`hr_users.company_id`** must stay in sync for HR; treat it as a **derived/operational** copy for HR-scoped queries.
- **Resolution rule:** Effective `company_id` = non-empty `hr_users.company_id` if present, else `profiles.company_id`; on read, **sync** `hr_users` from profile when profile has `company_id` and role is HR.

---

## Implementation (this change set)

1. **`get_hr_company_id`:** Fall back to `profiles.company_id` when `hr_users.company_id` is null/empty.
2. **`sync_hr_user_company_from_profile`:** On `GET /api/hr/company-profile`, call `ensure_hr_user_for_profile` when profile is HR and has `company_id`.
3. **`save_company_profile`:** After save, `ensure_hr_user_for_profile` for HR so missing `hr_users` rows are created.
