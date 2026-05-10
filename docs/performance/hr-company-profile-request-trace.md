# HR Company Profile — Request Trace

**Date:** 2025-03-17  
**Page:** `/hr/company-profile`  
**Purpose:** Trace all requests fired when HR opens Company Profile.

---

## Request Sequence on Initial Page Load

### Direct navigation (e.g. bookmark, direct URL)

| # | Endpoint | Source | Trigger | Critical for first paint? |
|---|----------|--------|---------|---------------------------|
| 1 | GET /api/company | CompanyBrand (AppShell) → useCompany | useEffect on mount | **No** — header branding only |
| 2 | GET /api/hr/company-profile | HrCompanyProfile | useEffect on mount | **Yes** — form data |

**Total:** 2 requests for Company Profile itself.

---

### Navigation from /hr/dashboard

When HR lands on dashboard first (default post-login), then clicks "Company Profile":

**Dashboard (before navigation):**
- `loadAssignments(ac.signal)` → GET /api/hr/assignments
- `hrAPI.getCompanyProfile()` → GET /api/hr/company-profile (redirect check; no AbortController)
- After listAssignments: `loadAssignmentDetails(data, 5, signal)` → 5× GET /api/hr/assignments/{uuid}

**On navigation to Company Profile:**
- HrDashboard unmounts → `ac.abort()` cancels listAssignments and the 5 getAssignment calls
- **getCompanyProfile from dashboard has no AbortController** — continues in flight
- HrCompanyProfile mounts → GET /api/hr/company-profile
- CompanyBrand → GET /api/company (or cached)

**Result:** User may see in Network tab:
- /api/hr/assignments (canceled or completing)
- 5× /api/hr/assignments/{uuid} (canceled or completing)
- 1–2× /api/hr/company-profile (dashboard + page)
- 1× /api/company

---

## Component/Hook → Request Mapping

| Component | Hook/API | Endpoint | When |
|-----------|----------|----------|------|
| AppShell | — | — | (wrapper) |
| CompanyBrand | useCompany → companyAPI.get | GET /api/company | When (isHrRole \|\| isEmployeeRole) && !showAdminContextOnly && role !== 'ADMIN' |
| HrCompanyProfile | hrAPI.getCompanyProfile | GET /api/hr/company-profile | On mount |
| useAdminContext | adminAPI.getContext | GET /api/admin/context | ADMIN only; not on company-profile when HR |
| EmployeeAssignmentProvider | employeeAPI.getCurrentAssignment | GET /api/employee/assignments/current | **Gated:** only when path starts with /employee |

---

## Redundant / Duplicate Requests

1. **Two company data sources**
   - `/api/company` (CompanyBrand) — uses `get_company_for_user` (profile-based)
   - `/api/hr/company-profile` (page) — uses `_get_hr_company_id` then `get_company`
   - For HR, different resolution paths; both return company data.

2. **getCompanyProfile on HrDashboard**
   - Dashboard fetches company profile solely to redirect if no company.
   - Adds extra /api/hr/company-profile when user lands on dashboard first.

3. **No shared company context**
   - Each component fetches company independently.
   - No reuse of company_id or company payload across HR pages.

---

## Required vs Deferred vs Unnecessary

| Request | Required for Company Profile first paint? | Action |
|---------|------------------------------------------|--------|
| company_id / HR context | **Yes** | Resolve once, reuse |
| company profile (form fields) | **Yes** | Single fetch |
| /api/company (header) | **No** — can derive from profile | Skip on HR company-profile; use profile data or shared context |
| assignments | **No** | Never load on Company Profile |
| assignments/{uuid} | **No** | Never load on Company Profile |
| employees | **No** | Never load on Company Profile |
| admin/context | **No** | ADMIN only |

---

## UUID Request Fan-Out Source

The "many UUID-style requests" (e.g. `/api/hr/assignments/{uuid}`) are triggered by:

- **HrDashboard.loadAssignmentDetails** — one GET per assignment (up to 5 after recent fix)
- Fires **after** listAssignments completes
- When user navigates to Company Profile before completion, these may still be in flight
- **Fix:** Abort on unmount (already done). Ensure Company Profile never triggers assignments.

---

## Recommendations (Implementation)

1. **Single HR company context** — Resolve company_id once, cache, reuse for profile, employees, assignments, header.
2. **Skip /api/company on HR company-profile** — Use company from getCompanyProfile or shared context for CompanyBrand.
3. **Abort HrDashboard getCompanyProfile on unmount** — Add AbortController to second useEffect.
4. **Backend: /api/company for HR** — Use `get_hr_company_id` when user is HR, not `get_company_for_user`.
5. **Route-scoped loading** — Assignments/employees only on their pages, never on Company Profile.
