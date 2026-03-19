# HR Company Profile — Fix Results

**Date:** 2025-03-17  
**Page:** `/hr/company-profile`

---

## Summary of Changes

### Phase 1–2: Documentation
- **Data model audit** (`hr-company-profile-data-model-audit.md`): Canonical HR company resolution path, schema relationships, gaps.
- **Request trace** (`hr-company-profile-request-trace.md`): Full request sequence, component mapping, required vs deferred.

### Phase 3: Canonical HR Company Context
- **HrCompanyContextProvider** + **useHrCompanyContext()**: Single resolution of `company_id` and company profile for HR routes.
- **CompanyBrand**: Uses HR context when on HR routes; skips `/api/company` to avoid duplicate fetch.
- **HrCompanyProfile**: Consumes context instead of its own fetch; no separate `getCompanyProfile` call.
- **useCompany**: Added `skip` option; CompanyBrand passes `skip: true` when using HR context.

### Phase 4–5: Data Loading
- Company Profile loads only core profile data (single fetch via context).
- Assignments and employees never load on Company Profile; they remain on their own pages.
- Backend `/api/company` uses `get_hr_company_id` for HR users instead of `get_company_for_user`.

### Phase 6–7: Assignments / UUID Fan-Out
- Assignments load only on HrDashboard; Company Profile does not trigger them.
- HrDashboard uses `AbortController` for `loadAssignments` and `loadAssignmentDetails`; requests cancel on unmount.
- HrDashboard `getCompanyProfile` redirect check: added `mounted` guard to avoid state updates after unmount.

### Phase 8–9: Backend
- `/api/company`: HR users resolved via `_get_hr_company_id`.
- Indexes: `idx_hr_users_company_id`, `idx_employees_company_id` added in `render_performance_indexes.sql`.

### Phase 10–11: Instrumentation & UX
- HrCompanyContext tracks request start/end via `trackRequestStart` / `trackRequestEnd`.
- Shell renders immediately; form shows skeletons while loading; no page-wide blocking spinner.

---

## Before / After Request Counts (Company Profile)

| Scenario | Before | After |
|----------|--------|-------|
| Direct load /hr/company-profile | 2 (api/company + api/hr/company-profile) | **1** (api/hr/company-profile via context) |
| Navigate from /hr/dashboard | 2 + in-flight assignments + 5× UUID details | **1** + dashboard requests aborted on nav |

---

## Requests Removed

1. **`GET /api/company`** on HR routes — CompanyBrand uses HrCompanyContext when `isHrUser && isOnHrRoute`; `useCompany` is called with `skip: true`.
2. **Duplicate `GET /api/hr/company-profile`** — Single fetch in HrCompanyContext; HrCompanyProfile and CompanyBrand both use the result.
3. **HrDashboard redirect `getCompanyProfile`** — Still runs on dashboard; no longer leaves a stray request when navigating away (mounted guard prevents redirect after unmount).

---

## Verification

- Company context is resolved once per HR session and reused.
- Assignments and employees stay company-scoped and load only on their pages.
- UUID fan-out is limited to HrDashboard; navigation aborts in-flight requests.
- Instrumentation: set `VITE_PERF_DEBUG=1` to log `[page-perf]` entries for route entry, shell render, and request timing.

---

## Next Steps (Optional)

1. Add a lightweight `GET /api/hr/company-context` returning only `{ company_id, name, logo_url }` for header branding, if needed.
2. Revisit `list_hr_assignments` N+1 (per-assignment compliance report) if latency persists.
3. Apply indexes via `render_performance_indexes.sql` in production if not already applied.
