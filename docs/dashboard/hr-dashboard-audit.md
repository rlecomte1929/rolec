# HR Dashboard / Command Center Audit

**Date:** 2025-03-19  
**Purpose:** Document current information architecture, dependencies, and identify causes of slow load.

---

## Route/Component Map

| Route | Component | Primary Content |
|-------|-----------|-----------------|
| `/hr/dashboard` | HrDashboard | Assignments list (create, assign, filter, manage) |
| `/hr/command-center` | HrCommandCenter | KPI cards + cases table |

Nav label "Assignments" → hrDashboard; "Dashboard" → hrCommandCenter. The user's "HR dashboard" refers to **Command Center** (`/hr/command-center`).

---

## Request Sequence on Command Center Entry

| # | Request | Caller | When |
|---|---------|--------|------|
| 1 | GET /api/hr/company-profile | HrCompanyContextProvider (AppShell parent) | On any /hr route |
| 2 | GET /api/hr/command-center/kpis | HrCommandCenter useEffect | On mount |
| 3 | GET /api/hr/command-center/cases | HrCommandCenter useEffect | On mount (Promise.all with KPIs) |

**Note:** `/api/hr/employees` is NOT called by Command Center. It is only called by HrEmployees page. The 400 on employees does not block the dashboard but may appear in network tab if user navigated from Employees or if something else triggers it.

---

## Widget-to-Endpoint Dependency Map

| Widget | Endpoint | Dependency |
|--------|----------|------------|
| All 9 KPI cards | /api/hr/command-center/kpis | Single shared response |
| Cases table | /api/hr/command-center/cases | Paginated list |
| Company branding (header) | /api/hr/company-profile (via HrCompanyContext) | Decorative; not needed for dashboard content |

---

## KPI Cards (Current)

| KPI | Source | Reliability | Notes |
|-----|--------|-------------|-------|
| Active Cases | assignments count | ✓ | Filter status not in (closed, rejected) |
| Action Required | status=submitted OR compliance check | ⚠ | Per-assignment get_latest_compliance_report — expensive |
| Departing Soon | employee profile movePlan.targetArrivalDate | ⚠ | Per-assignment get_employee_profile — expensive |
| Completed (YTD) | status=approved, created_at this year | ✓ | Simple |
| At Risk | risk_status=red | ✓ | Simple |
| Attention Needed | risk_status=yellow | ✓ | Simple |
| Overdue Tasks | relocation_tasks WHERE status=overdue | ⚠ | N queries (one per assignment) |
| Avg. Visa Duration | — | ✗ | Placeholder only, always "—" |
| Budget Overruns | budget_estimated > budget_limit | ✓ | Simple |

---

## High-Value vs Low-Value vs Placeholder

| Category | KPIs |
|----------|------|
| **High-value, cheap** | Active Cases, Completed (YTD), At Risk, Attention Needed, Budget Overruns |
| **High-value, expensive** | Action Required (compliance), Departing Soon (profile), Overdue Tasks (N+1) |
| **Placeholder** | Avg. Visa Duration |
| **Cases list** | High-value; currently does N+1 (task query per row) |

---

## Critical vs Non-Critical Dependencies

| Dependency | Critical for first paint? | Blocks? |
|------------|---------------------------|---------|
| company-profile | No (header only) | No — CompanyBrand returns null until loaded |
| KPIs | Yes | Yes — whole page shows "Loading..." until Promise.all completes |
| Cases | Yes | Yes — same Promise.all |

---

## Data Scoping Issue

**Current:** Command center uses `hr_user_id` — assignments created by this HR user only.

**Expected:** Company-scoped — all assignments for the HR user's company (same as list_assignments, admin company detail).

The main `/api/hr/assignments` uses `company_id` when available (`_get_hr_company_id`). Command center does not — it uses `hr_user_id` only. **Incoherent:** Assignments page may show company-wide cases; Command Center shows only "my" cases.

---

## Likely Causes of Slow First Render (Addressed)

1. ~~**No shell:**~~ Fixed: KPI cards and cases section render immediately with placeholders/skeleton.
2. ~~**Blocking Promise.all:**~~ Fixed: KPIs and cases load independently; each streams in when ready.
3. ~~**KPI N+1:**~~ Fixed: Removed per-assignment compliance/profile; single overdue aggregate.
4. ~~**Cases N+1:**~~ Fixed: Batch task stats query per page.
5. **KPI fetches all assignments:** Still loads all for aggregation; acceptable for typical company sizes.
6. **company-profile:** Fires on /hr routes; decorative only, does not block dashboard content.
