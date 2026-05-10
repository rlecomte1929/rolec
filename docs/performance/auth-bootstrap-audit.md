# Auth / Bootstrap Flow Audit

**Date:** 2025-03-17  
**Target page:** `/hr/company-profile` and initial protected page load  
**Goal:** Reduce latency from auth and post-auth bootstrap.

---

## Current Auth Flow Sequence

### 1. Sign-in (Login)

1. User submits credentials on `/auth`
2. `authAPI.login(payload)` → `POST /api/auth/login` (backend validates, returns token + user)
3. `setSession(token, user)` → stores in localStorage (`relopass_token`, `relopass_user_id`, `relopass_email`, `relopass_role`, etc.)
4. **`signInSupabase(email, password)`** → `supabase.auth.signInWithPassword()` — **blocks ~0.86–0.91 s** (token?grant_type=... in Network)
5. `redirectByRole()` → navigates to `/hr/dashboard` or `/employee/dashboard`

**Finding:** Supabase sign-in runs **before** redirect. The user sees no UI change until both backend login and Supabase sign-in complete. Supabase is used for feedback, review, RPC—not primary auth.

### 2. Token Refresh / Session Retrieval

- **Backend:** Uses JWT-like token from `relopass_token`; no server-side refresh endpoint for our custom auth.
- **Supabase:** `supabase.auth.getSession()` (and implicit refresh) is triggered when feedback/review/rpc modules run. Not called during initial HR company-profile load unless those features are used.
- **Token reuse:** Token is read from localStorage per request via axios interceptor; no explicit refresh.

### 3. Protected Route / Guard

- **No explicit route guard.** HR pages render directly; auth is implicit:
  - Protected API calls use `Authorization: Bearer <token>`
  - 401 responses trigger `clearAuthItems()` and redirect to `/auth`
- **AppShell** reads `getAuthItem('relopass_role')` from localStorage—no network call.

### 4. Post-Login Bootstrap on `/hr/company-profile`

When user lands on `/hr/company-profile`:

| Component | Fetches | Blocking? | Notes |
|-----------|---------|-----------|-------|
| **AppShell** | `useAdminContext()` → `adminAPI.getContext()` | No | 403 for HR-only users (wasted request) |
| **AppShell** | `CompanyBrand` → `useCompany()` → `companyAPI.get()` | No (header) | Cached 60s, in-flight dedup |
| **HrCompanyProfile** | `hrAPI.getCompanyProfile()` | **Yes** | Page shows "Loading company profile..." until done |
| **EmployeeAssignmentProvider** | `employeeAPI.getCurrentAssignment()` | No | Only for EMPLOYEE/ADMIN; HR skips |

**Critical path:** `hrAPI.getCompanyProfile()` blocks first meaningful render of the company profile form.

---

## Duplicate Calls Found

1. **`/api/company` vs `/api/hr/company-profile`**
   - `companyAPI.get()` → `/api/company` (header branding: name, logo)
   - `hrAPI.getCompanyProfile()` → `/api/hr/company-profile` (full HR profile for form)
   - Different endpoints; both hit `db.get_company_for_user` or similar. Overlap in data but no sharing.

2. **`useAdminContext` for HR users**
   - Fetches `/api/admin/context` for both ADMIN and HR
   - Backend `require_admin` returns 403 for HR-only users
   - Wasted network round-trip on every HR page load

3. **`useCompany` / CompanyBrand**
   - Renders only when `(isHrRole || isEmployeeRole) && !showAdminContextOnly && role !== 'ADMIN'`
   - For HR on `/hr/company-profile`: runs; fetches company (cached 60s)

---

## Blocking Requests in Critical Path

1. **Sign-in:** `signInSupabase` blocks redirect (~0.9 s)
2. **HrCompanyProfile:** Full page blocks on `getCompanyProfile` (2.5–8.5 s observed)
3. **Assignments** (on other HR pages): `hrAPI.listAssignments` blocks HrDashboard, HrAssignmentReview, HrComplianceCheck (34+ s observed, sometimes fails)

---

## Highest-Probability Causes of Latency

1. **Supabase sign-in on login** — Blocks redirect; can be deferred to after navigation.
2. **`useAdminContext` 403 for HR** — Unnecessary request on every HR page.
3. **HrCompanyProfile blocks on full profile** — Page could render shell immediately, load profile in background.
4. **Assignments on dashboard** — `list_assignments` is heavy (DB joins, compliance reports); blocks entire dashboard. Not used on company-profile but is on other HR pages.
5. **No shared company-profile cache** — `getCompanyProfile` not cached; every mount triggers a fresh request.

---

## Assignments Trace

- **Called by:** HrDashboard, HrAssignmentReview, HrComplianceCheck, AdminOverviewPage, AdminAssignments
- **Not called by:** HrCompanyProfile
- **Backend:** `GET /api/hr/assignments` → `db.list_assignments_for_company` or `list_assignments_for_hr` or `list_all_assignments`; bulk compliance report lookups; relocation_cases join
- **Slowness source:** Likely DB (complex queries, N+1 or bulk compliance), not frontend
- **Recommendation:** Move assignments off critical path on HR dashboard; show shell first, load assignments in background with skeleton.
