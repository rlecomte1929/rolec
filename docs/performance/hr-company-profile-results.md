# HR Company Profile — Performance Optimization Results

**Date:** 2025-03-17  
**Page:** `/hr/company-profile`  
**Scope:** Request audit, instrumentation, duplicate removal, critical-path reduction, backend optimization.

---

## Before/After Timings

| Metric | Before (observed) | After (expected) |
|--------|-------------------|------------------|
| company | ~7 s | ~7 s (backend optimization pending; indexes added) |
| company-profile | ~8 s | ~8 s (backend optimization pending; indexes added) |
| assignments on company-profile | 1 + up to 20 UUID requests | **0** (no longer triggered) |
| 46–48 s hanging requests | Many | **Reduced** (abort on unmount, batch 5 not 20) |
| Initial requests on company-profile | company + company-profile + assignments* + 20× details* | company + company-profile only |
| Shell first render | Blocked by profile | **Immediate** (skeleton) |

*When navigating from dashboard; now aborted on route change.

---

## Requests Removed from Initial Load

| Request | Source | Change |
|---------|--------|--------|
| GET /api/hr/assignments | HrDashboard (in-flight after nav) | Aborted on unmount |
| GET /api/hr/assignments/{uuid} (×20) | HrDashboard loadAssignmentDetails | Aborted on unmount; batch reduced 20→5 |
| GET /api/employee/assignments/current | EmployeeAssignmentProvider | Only on `/employee/*` routes |
| useCompany (duplicate) | HrCompanyProfile | Removed; use getCompanyProfile for logo |

---

## Requests Deduplicated

1. **useCompany on HrCompanyProfile** — Removed. Logo comes from getCompanyProfile.
2. **Company API** — Still used by CompanyBrand in header; cached 60s, in-flight dedup.
3. **getCompanyProfile** — Cached 60s; invalidated on save/logo change.

---

## Endpoints Instrumented

- **Frontend:** `perf/pagePerf.ts` — route entry, shell render, request start/end, first meaningful content.
- **Backend:** `_log_endpoint_perf()` when `PERF_DEBUG=1`:
  - `/api/company`
  - `/api/hr/company-profile`
  - `/api/hr/assignments` (success and 500)

---

## Cause of ~47 Second Requests

**Root cause:** HrDashboard issued up to 20 parallel `GET /api/hr/assignments/{uuid}` requests after listAssignments. With a 6-connection-per-origin limit, requests queued. When the user navigated to company-profile, those requests were not aborted and continued in the background, contributing to the 46–48 s pattern.

**Fixes applied:**
1. **AbortController** — Dashboard requests aborted on unmount.
2. **Smaller batch** — Initial detail load 5 instead of 20.
3. **Route-scoped fetching** — EmployeeAssignmentProvider only fetches on `/employee/*`.

---

## 500 Error

**Status:** Not yet pinpointed. The assignments endpoint can return 500 on exception; other endpoints may as well.

**Instrumentation:** `PERF_DEBUG=1` logs `[endpoint-perf]` JSON for company, company-profile, assignments (including 500).

**Recommendation:** Reproduce with `PERF_DEBUG=1`, inspect logs for `status_code: 500`, and fix the failing handler. Common sources: compliance report, policy resolution, or DB errors in the assignments loop.

---

## CORS Preflight

**Cause:** `Authorization: Bearer` and `X-Request-ID` on every request trigger preflight for cross-origin calls. This is required for auth and correlation.

**Change:** No code change. Reducing the number of requests (abort, route gating, smaller batch) lowers the total number of preflights. Same-origin proxy would remove preflight but needs infra changes.

---

## Backend Optimizations

1. **Indexes** (in `backend/sql/render_performance_indexes.sql`):
   - `idx_profiles_company_id` — profiles.company_id
   - `idx_hr_users_profile_id` — hr_users.profile_id
   - `idx_relocation_cases_company_id` — relocation_cases.company_id

2. **Structured perf logs** — `_log_endpoint_perf()` when `PERF_DEBUG=1`.

---

## Remaining Optimizations

1. **Backend company/profile latency** — ~7–8 s; profile/company queries need review (joins, N+1, indexes).
2. **Assignments endpoint** — `get_latest_compliance_report` per assignment may cause N+1; consider batching.
3. **500 identification** — Use `PERF_DEBUG` logs to find and fix failing endpoint(s).
4. **Optional:** Combine company + company-profile into a single bootstrap endpoint.

---

## Manual Verification Checklist (Chrome DevTools)

- [ ] **Request count** — Initial load of `/hr/company-profile` shows only `company` and `company-profile` (plus admin/context if ADMIN).
- [ ] **Assignments** — No `GET /api/hr/assignments` or `GET /api/hr/assignments/{uuid}` on company-profile.
- [ ] **Navigation from dashboard** — Going dashboard → company-profile does not leave assignments requests in flight (Network tab; aborted or completed quickly).
- [ ] **Shell** — Page shell (header, card, skeletons) renders before secondary requests finish.
- [ ] **Requests &gt; 5 s** — Check Network for any request still exceeding 5 s; inspect backend with `PERF_DEBUG=1`.
- [ ] **500s** — Confirm no 500 responses; if any, use `PERF_DEBUG` logs to locate the endpoint.

---

## Env Flags

- **Frontend:** `VITE_PERF_DEBUG=1` — Enables `[page-perf]` and `[auth-perf]` console logs.
- **Backend:** `PERF_DEBUG=1` — Enables `[endpoint-perf]` structured JSON logs for company, company-profile, assignments.
- **Backend:** `AUTH_PERF_DEBUG=1` — Enables auth-specific perf logs.
