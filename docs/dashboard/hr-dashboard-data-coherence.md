# HR Dashboard Data Coherence

**Date:** 2025-03-19  
**Purpose:** Document canonical source of dashboard truth and company scoping.

---

## Canonical Source of Dashboard Truth

The Command Center dashboard derives all data from **company-scoped case assignments** when the HR user has a company. The same scoping rules used by `/api/hr/assignments` and admin company detail are applied.

**Base filter:**
```sql
(rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
```
- `relocation_cases` (rc) joined via `case_id` / `canonical_case_id`
- `hr_users` (hu) joined via `hu.profile_id = ca.hr_user_id`
- When case has no `company_id`, fallback to HR user's company

---

## How Company Scoping Is Enforced

1. **Resolution:** `_get_hr_company_id(effective)` → `hr_users.company_id` or `profile.company_id`
2. **Preference:** When `company_id` is present, all command-center queries use company scope
3. **Fallback:** When no company (e.g. HR not yet linked), use `hr_user_id` (assignments created by this HR user)
4. **Admin:** When `hr_user_id` is None (admin, no impersonation), no scope filter — all cases

---

## How Each Visible KPI Is Computed

| KPI | Source | Query / Logic |
|-----|--------|---------------|
| Active Cases | Assignments | Count where status NOT IN (closed, rejected) |
| Action Required | Assignments | Count where status = 'submitted' |
| Departing Soon | Assignments | Count where expected_start_date within next 30 days |
| Completed (YTD) | Assignments | Count where status = 'approved' and created_at this year |
| At Risk | Assignments | Count where risk_status = 'red' |
| Attention Needed | Assignments | Count where risk_status = 'yellow' |
| Overdue Tasks | relocation_tasks | Single aggregate: COUNT where assignment_id IN (...) AND status = 'overdue' |
| Budget Overruns | Assignments | Count where budget_estimated > budget_limit |

---

## Removed or Deferred Metrics

| Metric | Reason |
|--------|--------|
| **Avg. Visa Duration** | Placeholder only, no data source; removed |
| **Action Required (compliance-based)** | Previously used per-assignment `get_latest_compliance_report`; simplified to status='submitted' only |
| **Departing Soon (profile-based)** | Previously used per-assignment `get_employee_profile`; now uses `expected_start_date` from case_assignments |

---

## Cases List

- Same company-scoped base query as KPIs
- Paginated (page, limit)
- Optional risk_filter
- Task stats (done %, next deadline) computed in **one batch query** per page (no N+1)
