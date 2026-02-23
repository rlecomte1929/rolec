# Plan: Move to Real Supabase Sign-In (Auto Token Refresh)

## Current State

| Component | Auth Mechanism | Token Lifecycle |
|-----------|----------------|-----------------|
| **Backend API** (hrAPI, employeeAPI) | Custom `relopass_token` (UUID) → `sessions` table | Long-lived, server-stored |
| **Supabase** (feedback, review, RPC) | `VITE_SUPABASE_ACCESS_TOKEN` fallback when no session | JWT expires ~1h, manual refresh |

**Problem:** Supabase calls use a static env token that expires. No refresh.

---

## Goal

Use Supabase Auth as the source of truth for Supabase-backed features. Tokens refresh automatically via `supabase.auth.onAuthStateChange` / `getSession()`.

---

## Phased Approach

### Phase 1: Supabase Sign-In for Supabase Features Only (Minimal)

**Scope:** Keep backend login for backend API. Add Supabase sign-in when user logs in, so Supabase session exists and auto-refreshes.

**Steps:**
1. **Backend returns Supabase credentials** – After backend login succeeds, backend calls Supabase Admin API to create a magic link or sign-in link for that email, OR we add a "Supabase login" step that runs in parallel.
2. **OR: Dual login on frontend** – On `authAPI.login()` success, call `supabase.auth.signInWithPassword({ email, password })` with same credentials. This requires users to exist in **both** backend `users` and Supabase `auth.users` with same email/password.
3. **Preferred: Backend-initiated Supabase session** – Backend has Supabase service role. On login success, backend generates a custom JWT or uses Supabase Admin `generateLink` to create a session, returns it to frontend. Frontend calls `supabase.auth.setSession()`. Complex.
4. **Simpler: Unify login to Supabase first** – Change login to call `supabase.auth.signInWithPassword()` only. On success, we have a Supabase session (auto-refresh). Then call backend with Supabase JWT; backend validates JWT and creates/returns a relopass_token for legacy API. Two tokens, but Supabase one refreshes.

**Recommended for Phase 1:** Option 4 – Supabase sign-in first, backend validates JWT and issues relopass_token for legacy.

---

### Phase 2: Supabase Auth as Single Source (Full Migration)

**Scope:** Remove backend auth; Supabase Auth is the only auth.

**Steps:**
1. **User sync** – Ensure all users exist in Supabase `auth.users`. Role in `user_metadata.role` or `public.profiles`.
2. **Backend accepts Supabase JWT** – Add dependency `python-jose` or `pyjwt`. Validate `Authorization: Bearer <jwt>` against Supabase JWT secret. Extract `sub` (user id) and role from JWT or DB lookup.
3. **Frontend** – Login only via `supabase.auth.signInWithPassword()`. Remove `authAPI.login()` for login flow. Store session via Supabase client (no manual token storage for Supabase).
4. **case_assignments alignment** – `hr_user_id` and `employee_user_id` must be Supabase `auth.users.id` (UUID). If backend used different IDs, migration needed.
5. **Remove** – `sessions` table usage for login, `relopass_token`, `VITE_SUPABASE_ACCESS_TOKEN` fallback.

---

### Phase 1 Implementation Checklist (Minimal Change)

- [ ] **1.1** Ensure test users exist in Supabase Auth with same email/password as backend.
- [x] **1.2** Update `useAuth.login()` and `SwitchUserModal` to call `signInSupabase()` after backend login succeeds. Supabase session established → `getSession()` returns it → feedback/review/rpc use it.
- [x] **1.3** `feedback.ts`, `review.ts`, `rpc.ts` already prefer `getSession()` over fallback. With real session, no fallback needed.
- [x] **1.4** On logout: `authAPI.logout()` now calls `signOutSupabase()` before `clearAuthItems()`.
- [x] **1.5** If Supabase sign-in fails (user not in Supabase), login still succeeds; console warning in dev. Supabase features fall back to `VITE_SUPABASE_ACCESS_TOKEN` if set.

---

### Phase 2 Implementation Checklist (Full Migration)

- [ ] **2.1** Create `public.profiles` (or use `user_metadata`) with `user_id`, `role`, `email`, `name`.
- [ ] **2.2** Backend: Add `get_current_user_from_supabase_jwt()` dependency.
- [ ] **2.3** Migrate backend login/register to validate Supabase JWT only; remove `sessions` for new logins.
- [ ] **2.4** Frontend: Remove `authAPI.login()` for login; use only `supabase.auth.signInWithPassword()`. Use `session.access_token` for backend API calls.
- [ ] **2.5** Backend: Change `Authorization` handling to accept Supabase JWT.
- [ ] **2.6** Remove `VITE_SUPABASE_ACCESS_TOKEN`, `relopass_token` (or keep relopass_token for gradual backend cutover).
- [ ] **2.7** Add Supabase Auth UI for forgot password, email confirmation if needed.

---

## File Touch Points

| File | Phase 1 | Phase 2 |
|------|---------|---------|
| `frontend/src/hooks/useAuth.ts` | Add Supabase signIn before/after backend login | Replace with Supabase-only login |
| `frontend/src/api/client.ts` | Optional: send Supabase JWT to backend | Use Supabase session token for API |
| `frontend/src/api/feedback.ts` | No change if session exists | Remove fallback |
| `frontend/src/api/review.ts` | No change if session exists | Remove fallback |
| `frontend/src/api/rpc.ts` | No change if session exists | Remove fallback |
| `backend/main.py` | Optional: accept Supabase JWT as alternative | Validate Supabase JWT only |
| `frontend/.env.development` | Keep fallback for edge cases | Remove VITE_SUPABASE_ACCESS_TOKEN |

---

## Quick Win (Phase 1.2)

**Minimal code change:** In `useAuth.login()`, after `authAPI.login()` succeeds:

```ts
// After setSession(response.token, response.user):
const { data: { user } } = await supabase.auth.signInWithPassword({
  email: response.user.email ?? identifier,
  password: payload.password,
});
// Supabase client now has session; it will auto-refresh.
```

**Requirement:** User must exist in Supabase Auth with same email/password. Create them manually in Supabase Dashboard or run a one-time migration to sync backend users → Supabase Auth (via Admin API).

---

## Rollout Order

1. **Sync users to Supabase Auth** (one-time script or manual for test users).
2. **Implement Phase 1.2** in useAuth.
3. **Test** – Login, open /hr/review, verify no JWT expired.
4. **Optional:** Remove `VITE_SUPABASE_ACCESS_TOKEN` from .env once confident.
5. **Later:** Phase 2 when ready to deprecate backend auth fully.
