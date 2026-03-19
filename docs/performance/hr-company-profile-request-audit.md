# HR Company Profile Page — Request Chain Audit

**Date:** 2025-03-17  
**Page:** `/hr/company-profile`  
**Observed:** company ~7s, company-profile ~8s, assignments ~23s, many UUID requests, 46–48s hangs, 500 error, GET+Preflight.

---

## Request Dependency Graph

```
App mount
├── SelectedCaseProvider (no network)
├── EmployeeAssignmentProvider
│   └── GET /api/employee/assignments/current  [if EMPLOYEE or ADMIN]
├── ServicesFlowProvider (no network on mount)
└── Route: HrCompanyProfile
    └── AppShell
        ├── useAdminContext
        │   └── GET /api/admin/context  [ADMIN only]
        ├── CompanyBrand (when HR non-ADMIN)
        │   └── useCompany → GET /api/company
        └── children
    └── HrCompanyProfile
        ├── useCompany → GET /api/company  [duplicate call, cache dedupes]
        └── hrAPI.getCompanyProfile() → GET /api/hr/company-profile
```

**Scenario: User navigates from /hr/dashboard to /hr/company-profile**

When HR login redirects to `/hr/dashboard`, HrDashboard mounts and starts:
- `loadAssignments()` → GET /api/hr/assignments (~23s)
- `hrAPI.getCompanyProfile()` → GET /api/hr/company-profile (redirect check)
- After listAssignments resolves: `loadAssignmentDetails(data, 20)` → **20× GET /api/hr/assignments/{uuid}** (parallel)

If user navigates to `/hr/company-profile` before these complete:
- HrDashboard unmounts but **requests are NOT aborted** (no AbortController)
- All dashboard requests remain in flight and appear in Network tab
- HrCompanyProfile mounts and starts its own requests

**Result:** On company-profile, user sees dashboard-originated assignments + 20× UUID detail requests + company-profile requests.

---

## Source Component/Hook per Request

| Request | Endpoint | Source | Trigger |
|---------|----------|--------|---------|
| company | GET /api/company | CompanyBrand (AppShell), HrCompanyProfile useCompany | useEffect on mount |
| company-profile | GET /api/hr/company-profile | HrCompanyProfile | useEffect on mount |
| assignments | GET /api/hr/assignments | HrDashboard (if navigated from) | useEffect on mount |
| assignments/{uuid} | GET /api/hr/assignments/{id} | HrDashboard loadAssignmentDetails | After listAssignments; up to 20 parallel |
| admin/context | GET /api/admin/context | AppShell useAdminContext | useEffect (ADMIN only) |
| employee/assignments/current | GET /api/employee/assignments/current | EmployeeAssignmentProvider | useEffect (EMPLOYEE/ADMIN only) |

---

## Critical vs Non-Critical

| Request | Critical for company-profile first paint? | Notes |
|---------|------------------------------------------|-------|
| company | **Marginally** — header branding only | CompanyBrand can render without; show placeholder |
| company-profile | **Yes** — form data | Required for editable form; already deferred with skeleton |
| assignments | **No** | Not used on company-profile; from previous page or should not load |
| assignments/{uuid} | **No** | Dashboard detail fan-out; should not run on company-profile |
| admin/context | **No** | ADMIN only; sidebar/impersonation |
| employee/assignments/current | **No** | EMPLOYEE only; nav highlight |

---

## Duplicate Request Sources

1. **useCompany × 2**
   - HrCompanyProfile uses `useCompany()` for logo_url
   - CompanyBrand (in AppShell) uses `useCompany()` for header
   - Both call `companyAPI.get()` → same endpoint
   - **Mitigation:** `cachedRequest` dedupes; first wins, second hits cache. But two hook instances, two useEffects.

2. **company vs company-profile**
   - `/api/company` and `/api/hr/company-profile` both return company data
   - Different shapes: company has name/logo; company-profile has full form fields
   - Could consolidate: company-profile could supply header data, or company could be skipped on company-profile page.

3. **getCompanyProfile on HrDashboard**
   - HrDashboard calls `hrAPI.getCompanyProfile()` in useEffect just to check if company exists and redirect
   - Adds another company-profile request when user lands on dashboard first.

---

## Probable Top 5 Root Causes

### 1. **Request fan-out from HrDashboard**
HrDashboard fires `loadAssignmentDetails(data, 20)` — up to 20 parallel GETs for assignment details. With 6-connection-per-origin limit, requests queue. Slow backend + queue = 46–48s total. These requests persist when navigating away (no AbortController).

### 2. **Assignments and UUID requests from previous page**
Login → hrDashboard → assignments + 20× details start → user navigates to company-profile. Dashboard unmounts but requests continue. Network tab shows them as if they belong to company-profile.

### 3. **Backend latency (company, company-profile, assignments)**
- `get_company_for_user` → get_profile_record + get_company (two DB round-trips)
- `list_hr_assignments` → list_assignments + bulk cases + per-assignment compliance report (N+1 risk)
- `get_assignment` (detail) → multiple lookups per assignment
- Possible missing indexes, connection pool exhaustion, or cold starts.

### 4. **CORS preflight for every request**
All API calls use `Authorization: Bearer` + `X-Request-ID`. Cross-origin + non-simple headers = preflight per request. Many requests = many preflights (2× round-trips per call).

### 5. **500 error — unknown endpoint**
At least one request returns 500. Needs log inspection. Candidates: compliance report, assignment detail, policy resolution, or an optional feature endpoint.

---

## Data Flow Summary

| Page load path | Requests on company-profile |
|----------------|----------------------------|
| Direct navigation (bookmark/link) | company, company-profile, [+ admin/context if ADMIN] [+ employee/current if EMPLOYEE/ADMIN] |
| From hrDashboard | Above + assignments + up to 20× assignments/{uuid} (in-flight from dashboard) |

---

## Recommendations (for implementation)

1. **Gate EmployeeAssignmentProvider** — Only fetch on employee routes, not on HR-only pages.
2. **Abort in-flight requests on HrDashboard unmount** — Use AbortController; cancel loadAssignments and loadAssignmentDetails.
3. **Lazy-load assignment details** — Load first 3–5, then load more on scroll or explicitly. Avoid 20 parallel requests.
4. **Skip company fetch on company-profile** — Use getCompanyProfile for both form and logo; avoid duplicate company endpoint.
5. **Route-scoped data loading** — Ensure assignments and related APIs only run when user is on dashboard/assignment pages.
6. **Backend** — Add indexes, reduce N+1, consider returning minimal assignment list without per-item compliance in first response.
7. **Identify and fix 500** — Add instrumentation, reproduce, fix handler.
