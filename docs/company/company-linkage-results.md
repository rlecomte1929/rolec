# Company linkage — results

**Date:** 2025-03-20

---

## Root cause

`database.get_hr_company_id` returned `hr_users.company_id` whenever **any** `hr_users` row existed for the profile. If that column was **NULL**, it returned `None` and **never** read `profiles.company_id`, where Admin assignment correctly stores the link. `GET /api/hr/company-profile` then loaded `get_company(None)` / missed the canonical company and returned `company: null` → empty HR form.

Secondary gap: if `hr_users` row was missing, `set_profile_company`’s `UPDATE hr_users` no-oped; HR save now calls `ensure_hr_user_for_profile` so the row is created.

---

## Final canonical model

- **Single table `companies`** for all company profile fields (name, legal_name, country, hq_city, etc.).
- **`profiles.company_id`** defines which company the user belongs to.
- **`hr_users`** mirrors `company_id` for HR operational queries; kept aligned via `ensure_hr_user_for_profile` and `sync_hr_user_company_from_profile`.

---

## What was fixed (code)

| Area | Change |
|------|--------|
| `database.get_hr_company_id` | Fall back to `profiles.company_id` when `hr_users.company_id` is empty |
| `database.sync_hr_user_company_from_profile` | New: for role HR + profile `company_id`, call `ensure_hr_user_for_profile` |
| `GET /api/hr/company-profile` | Call sync before resolving company; optional `PERF_DEBUG` log when company loads |
| `POST /api/hr/company-profile` | After save, `ensure_hr_user_for_profile` for HR users |

---

## Admin / HR edit coherence

- **Same row:** Both Admin (`PATCH /api/admin/companies/{id}`) and HR (`POST /api/hr/company-profile`) upsert **`companies`** via `create_company` / `update_company` patterns.
- **Field ownership:** Not split by table; HR form maps to the same columns Admin uses where overlapping. Admin-only fields (e.g. plan_tier, seat limits) remain Admin API only.

---

## Load path (efficient)

- Still **one** primary request: `GET /api/hr/company-profile`.
- Extra work on read: one profile read + optional `hr_users` update (sync) — no fan-out of company discovery calls.

---

## Manual verification checklist

- [ ] Admin creates company with a **name** (and optional fields).
- [ ] Admin assigns HR user to that company (`assign-company`).
- [ ] HR opens `/hr/company-profile` → **company name** (and other stored fields) are prefilled.
- [ ] Admin changes company name → HR refreshes → sees updated name.
- [ ] HR saves profile → Admin company detail shows consistent data where fields overlap.
- [ ] No new orphan `companies` row when HR only edits existing linked company.

---

## Instrumentation

- Set `PERF_DEBUG=1` to log `company_profile_loaded` with `user_id`, `company_id`, `name` on successful load.
