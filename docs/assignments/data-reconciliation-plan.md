# Data Reconciliation Plan

**Date:** 2025-03-19  
**Purpose:** Document categories of potentially inconsistent data from prior assignment flows, remediation logic, and what requires manual review.

---

## Categories of Bad Data (Potential)

### 1. Assignments with null case company_id

- **Symptom:** `relocation_cases.company_id` is null; assignment visible only via `hr_users.company_id`.
- **Cause:** Case created before company was set; assign_case didn't always upsert case with company.
- **Impact:** `list_assignments_for_company` still includes these (fallback: `hu.company_id = :cid`).
- **Remediation:** Admin endpoint `POST /api/admin/reconciliation/link-assignment-company` exists; can set `relocation_cases.company_id` via case.

### 2. HR users with divergent company_id

- **Symptom:** `hr_users.company_id` ≠ `profiles.company_id` for same HR user.
- **Cause:** Admin assigned company to profile but hr_users wasn't updated, or vice versa.
- **Impact:** List uses `_get_hr_company_id` (hr_users first); assign/create previously used profile only. Now unified.
- **Remediation:** `db.set_profile_company` and `ensure_hr_user_for_profile` sync both. Admin "Assign company" flow should keep them aligned.

### 3. Duplicate employee rows

- **Symptom:** Multiple `employees` rows for same real person (e.g. same email, different profile_id).
- **Cause:** Multiple create paths; no unique constraint on (company_id, email) or similar.
- **Remediation:** Manual review; consider unique constraint on `employees` + `profiles` linkage. Reconciliation script could flag duplicates by email+company.

### 4. Assignments linked to wrong company

- **Symptom:** Assignment's case has `company_id` A, but HR owner belongs to company B.
- **Cause:** HR moved companies; assignment created before move; or manual data error.
- **Impact:** Would appear in company A's list (via case), not company B's.
- **Remediation:** Admin `link-assignment-company` to fix case company_id. Or reassign HR if intended.

### 5. Orphaned assignments

- **Symptom:** Assignment exists but case deleted, or hr_user_id points to deleted profile.
- **Cause:** Partial delete; FK not enforced.
- **Remediation:** Audit query to find assignments with missing case or HR profile; manual repair or soft-delete.

### 6. assignment_invites with no assignment_id

- **Current schema:** `assignment_invites` has `case_id`, `employee_identifier`; no `assignment_id`.
- **Impact:** Token-based claim would need join via case + identifier. Assignment-ID-in-URL flow works without it.
- **Remediation:** Optional migration to add `assignment_id` to `assignment_invites` for clarity; not required for current flow.

---

## Remediation Logic

### Automated (Script/Migration)

1. **Backfill case company_id from HR:**
   - For `relocation_cases` where `company_id` IS NULL: set from `hr_users.company_id` where `hr_users.profile_id = relocation_cases.hr_user_id`.

2. **Align hr_users and profiles company_id:**
   - For each hr_users row: if `profiles.company_id` differs, update `profiles.company_id = hr_users.company_id` (or vice versa based on policy).

3. **Flag duplicate employees:**
   - Query: same company_id + same email (from profiles) → list for manual review.

### Manual Review

- Duplicate employee records.
- Assignments with case from one company and HR from another (intentional vs error).
- Orphaned assignments.

---

## What Was Fixed Automatically vs Manual

| Category | Automatic | Manual |
|----------|-----------|--------|
| Case missing company_id | Admin reconciliation endpoint exists | Run for specific assignments |
| HR/profile company mismatch | set_profile_company syncs on Admin assign | One-off backfill if needed |
| Duplicate employees | — | Review and merge |
| Wrong company on assignment | link-assignment-company | Admin action |
| Orphaned assignments | — | Audit and fix |

---

## Reconciliation Endpoints (Existing)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/admin/reconciliation/link-assignment-company` | Set assignment's case company_id |
| `POST /api/admin/reconciliation/link-assignment-person` | Attach profile as employee to assignment |
| `POST /api/admin/reconciliation/link-person-company` | Link profile to company |
| `GET /api/admin/reconciliation/report` | Full reconciliation report |
| `GET /api/admin/companies/{id}` | orphan_diagnostics for company |

---

## References

- `backend/main.py`: reconciliation endpoints
- `backend/database.py`: get_company_detail_orphan_diagnostics, admin_fix_assignment_company_linkage
- `docs/assignments/assignment-domain-audit.md`
