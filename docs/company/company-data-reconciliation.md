# Company data reconciliation

**Date:** 2025-03-20

---

## Bad data categories

| Category | Symptom | Detection idea |
|----------|---------|------------------|
| **hr_users.company_id NULL, profile set** | HR company profile empty | `SELECT * FROM hr_users hu JOIN profiles p ON p.id = hu.profile_id WHERE p.role = 'HR' AND p.company_id IS NOT NULL AND (hu.company_id IS NULL OR TRIM(hu.company_id::text) = '')` |
| **profile.company_id points to missing companies row** | Form empty / 404-ish behavior | Left join companies; `companies.id IS NULL` |
| **Two companies for one org** | Admin sees one name, HR another | Manual: compare names / admin audit |
| **HR saved before Admin link** | Extra orphan `companies` row | `companies` with no assignments/policies/hr_users |

---

## Remediation strategy

1. **Runtime (implemented):** `sync_hr_user_company_from_profile` + fixed `get_hr_company_id` so correct `companies` row loads without manual SQL.
2. **Optional SQL backfill:** For each HR profile with `profiles.company_id` set and `hr_users.company_id` null:
   ```sql
   UPDATE hr_users hu
   SET company_id = p.company_id
   FROM profiles p
   WHERE hu.profile_id = p.id
     AND p.role = 'HR'
     AND p.company_id IS NOT NULL
     AND (hu.company_id IS NULL OR hu.company_id = '');
   ```
   (Adjust for SQLite vs Postgres types.)

---

## Auto-fix vs manual

| Auto-fix | Manual review |
|----------|----------------|
| NULL `hr_users.company_id` when profile has company | Duplicate `companies` representing same org |
| Missing `hr_users` row (ensure_hr_user_for_profile) | Merging two company IDs into one |
| Resolution order bug (code fix) | Orphan companies after bad HR first-save |

---

## Preserving edits

- Backfill SQL only fills **NULL** `hr_users.company_id`; it does not overwrite non-null values.
- Review before running updates in production.
