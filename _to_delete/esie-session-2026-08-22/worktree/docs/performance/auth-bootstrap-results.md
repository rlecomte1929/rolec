# Auth/Bootstrap Performance Optimization — Results

**Date:** 2025-03-17  
**Scope:** Auth/sign-in, token handling, protected-page bootstrap, critical-path reduction.

---

## What Was Changed

### 1. Supabase sign-in deferred after redirect

**File:** `frontend/src/hooks/useAuth.ts`

- Previously: `signInSupabase()` ran before `redirectByRole()` — ~0.9 s blocked before navigation.
- Now: Redirect happens immediately after backend login; Supabase sign-in runs in the background.
- Effect: User sees the dashboard almost immediately; Supabase session establishes asynchronously for feedback/review/RPC.

### 2. useAdminContext gated to ADMIN only

**File:** `frontend/src/features/admin/useAdminContext.ts`

- Previously: Fetched `/api/admin/context` for both ADMIN and HR — HR users received 403.
- Now: Only fetches when `role === 'ADMIN'`.
- Effect: Eliminates unnecessary 403 request on every HR page load.

### 3. HrCompanyProfile: shell first, profile deferred

**File:** `frontend/src/pages/HrCompanyProfile.tsx`

- Previously: Full page blocked on `getCompanyProfile`; showed "Loading company profile..." until done.
- Now: AppShell + Card render immediately with skeleton placeholders; profile loads in background; form populates when ready.
- Effect: Page becomes interactive in under ~100 ms; form fields appear as data arrives.

### 4. Company profile caching

**File:** `frontend/src/api/client.ts`

- `hrAPI.getCompanyProfile()` now uses `cachedRequest` with 60 s TTL and in-flight deduplication.
- Cache invalidated on `saveCompanyProfile`, `uploadCompanyLogo`, `removeCompanyLogo`.
- Effect: Repeat visits within 60 s avoid redundant requests.

### 5. Auth performance instrumentation

**Files:**
- `frontend/src/perf/authPerf.ts` — new module for auth bootstrap timing.
- `frontend/src/hooks/useAuth.ts` — tracks sign_in_click, auth_request_start/end, token_refresh_start/end.
- `frontend/src/pages/HrCompanyProfile.tsx` — tracks bootstrap_start/end.
- `frontend/src/pages/HrDashboard.tsx` — tracks bootstrap_start/end for listAssignments.

**Backend:** `backend/main.py` — `_log_auth_perf()` when `AUTH_PERF_DEBUG=1`; logs structured JSON for `/api/auth/login` with `endpoint`, `request_id`, `user_id`, `total_duration_ms`, `status_code`.

Instrumentation is off by default. Enable with:
- Frontend: `VITE_PERF_DEBUG=1`
- Backend: `AUTH_PERF_DEBUG=1`

### 6. HrDashboard skeleton for assignments

**File:** `frontend/src/pages/HrDashboard.tsx`

- Previously: Plain "Loading assignments..." text.
- Now: Skeleton rows matching the table layout.
- Effect: Perceived responsiveness improved during slow (e.g. 34+ s) assignments fetch.

### 7. Assignments trace (documentation only)

Assignments are **not** on the critical path for `/hr/company-profile`. They are loaded only on:
- HrDashboard (`/hr/dashboard`)
- HrAssignmentReview (`/hr/assignments/:id`)
- HrComplianceCheck
- AdminOverviewPage, AdminAssignments

Slowness (34+ s) is attributed to backend/DB (`list_assignments_for_company`, compliance lookups, joins). No change to assignments loading logic; shell + skeleton improve perceived performance.

---

## Duplicate Calls Removed

| Before | After |
|--------|-------|
| useAdminContext for HR → 403 on every page | useAdminContext only for ADMIN |
| Supabase sign-in blocking redirect | Supabase sign-in deferred, non-blocking |

---

## What Was Moved Off the Critical Path

| Endpoint / Feature | Before | After |
|--------------------|--------|-------|
| Supabase sign-in | Blocked redirect | Runs after redirect |
| HrCompanyProfile form | Blocked until getCompanyProfile | Shell + skeleton; profile loads in background |
| Admin context (HR) | Fetched, then 403 | Not fetched for HR |

---

## Before/After Timing Comparison

| Metric | Before (typical) | After (expected) |
|--------|------------------|------------------|
| Click sign-in → dashboard visible | ~1.5–2.5 s (backend + Supabase + redirect) | ~0.3–0.6 s (backend + redirect) |
| /hr/company-profile first interactive | 2.5–8.5 s (blocked on profile) | <0.2 s (shell) |
| /hr/company-profile form populated | 2.5–8.5 s | 2.5–8.5 s (unchanged, but page is usable) |

*Actual numbers depend on network and backend. Use `VITE_PERF_DEBUG=1` and `AUTH_PERF_DEBUG=1` to capture real measurements.*

---

## Remaining Bottlenecks

1. **Assignments API** — 34+ s on some loads; backend/DB optimization needed.
2. **getCompanyProfile** — Still 2.5–8.5 s in some cases; caching reduces repeat calls.
3. **Company/context fetches** — Parallel but not batched; potential for a single bootstrap endpoint.

---

## Recommended Next Target After Auth

1. **Backend: `GET /api/hr/assignments`** — Indexing, query simplification, pagination, or streaming.
2. **Backend: `GET /api/hr/company-profile`** — Profile query optimization.
3. **Frontend: Combined bootstrap** — Single endpoint returning company + profile + minimal context to reduce round-trips.

---

## Manual Verification Checklist (DevTools)

1. **Sign-in flow**
   - [ ] Click sign-in → redirect to dashboard within ~1 s.
   - [ ] Network: `token?grant_type=...` (Supabase) may appear after redirect.
   - [ ] Console (VITE_PERF_DEBUG=1): `[auth-perf] stage=auth_request_end`, `stage=token_refresh_end`.

2. **/hr/company-profile**
   - [ ] Page shell (header, card, skeletons) visible immediately.
   - [ ] Form fields populate when `getCompanyProfile` completes.
   - [ ] No blank white screen during load.

3. **HR dashboard**
   - [ ] Shell (search, filters, Create case) visible immediately.
   - [ ] Assignments list shows skeleton rows while loading.
   - [ ] No `/api/admin/context` request when logged in as HR (not ADMIN).

4. **Cache**
   - [ ] Navigate away from company-profile and back within 60 s → no new `getCompanyProfile` request (or cached).
   - [ ] Save profile → subsequent load fetches fresh data.
