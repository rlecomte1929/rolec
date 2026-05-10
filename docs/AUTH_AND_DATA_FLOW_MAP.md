# ReloPass Auth & Data Flow Map

## 1. Auth Stack

**Custom in-house auth** (no Supabase/NextAuth/Clerk):
- Backend: FastAPI + `passlib` (PBKDF2-SHA256) for password hashing
- Sessions: token-based, stored in `sessions` table
- Client: localStorage keys prefixed `relopass_*`

---

## 2. Auth Flow Locations

| Action | UI Location | API Endpoint | Notes |
|--------|-------------|--------------|-------|
| **Register** | `frontend/src/pages/Auth.tsx` (handleRegister) | `POST /api/auth/register` | `backend/main.py` ~L337 |
| **Login** | `frontend/src/pages/Auth.tsx` (handleLogin) | `POST /api/auth/login` | `backend/main.py` ~L395 |
| **Logout** | `frontend/src/components/AppShell.tsx` (Logout button) | None (client-only) | Clears localStorage, redirects to landing |
| **Session check** | Implicit on every API call | `Authorization: Bearer <token>` | `get_current_user` in main.py ~L302 |

---

## 3. Session Storage

- **Where**: `localStorage` (browser)
- **Keys**: `relopass_token`, `relopass_user_id`, `relopass_email`, `relopass_username`, `relopass_name`, `relopass_role`
- **Read/write**: `frontend/src/utils/demo.ts` (`getAuthItem`, `setAuthItem`, `clearAuthItems`)
- **Attached to requests**: `frontend/src/api/client.ts` axios interceptor (L41–46)

---

## 4. Current User Retrieval on Page Load

- No explicit "restore session" call
- Token is sent with first authenticated API request
- If API returns 401, individual pages call `safeNavigate(navigate, 'landing')` (no global 401 handler)
- `EmployeeAssignmentContext` checks `getAuthItem('relopass_token')` before loading assignments

---

## 5. Database & User Association

### Tables (backend/database.py)

| Table | Primary Key | Links To User |
|-------|-------------|---------------|
| `users` | `id` (TEXT UUID) | — |
| `sessions` | `token` | `user_id` → users.id |
| `profile_state` | `user_id` | users.id |
| `answers` | `id` (auto) | `user_id` → users.id |
| `relocation_cases` | `id` | `hr_user_id` → users.id |
| `case_assignments` | `id` | `hr_user_id`, `employee_user_id` → users.id |
| `employee_answers` | `id` | via assignment_id → case_assignments.employee_user_id |

### Lookup Chain

- **Login**: `identifier` (username or email) → `get_user_by_identifier` (tries username, then email)
- **Auth**: `token` → `sessions` → `user_id` → `users`
- **Profile/Answers**: `user_id` from token → `profile_state`, `answers`

---

## 6. Identified Risk Areas

1. **Email/username case sensitivity**: `get_user_by_email` and `get_user_by_username` use exact match; "User@Mail.com" vs "user@mail.com" may fail.
2. **No server-side logout**: Sessions are never invalidated; tokens persist in DB.
3. **No 401 interceptor**: Each page handles 401 individually; easy to miss.
4. **Duplicate registration check**: Uses exact match; case differences could allow duplicates.
5. **Two intake flows**: Journey (question_bank) vs CaseWizard (case draft); potential for confusion.

---

## 7. Root Cause Analysis (Auth Failures)

### Confirmed causes addressed

- **Email case sensitivity**: `get_user_by_email` now uses `LOWER(TRIM(email))`; registration stores email lowercase.
- **Username/email lookup**: `get_user_by_identifier` tries username first, then email; handles `@` for email.
- **No server-side logout**: Added `POST /api/auth/logout` and `delete_session_by_token`; client calls it before clearing localStorage.
- **Generic error messages**: Login/register now return specific messages (e.g. "Incorrect password", "Invalid username or email").

### Likely contributors (mitigated)

- **Session bloat**: Logout now invalidates token server-side.
- **401 not redirecting**: Added global axios interceptor to clear session and redirect to `/auth?mode=login`.

### Not the cause (verified)

- **Password hashing**: PBKDF2-SHA256 is consistent; no provider mismatch.
- **Duplicate user records**: Single `users` table; no auth.users vs public.users split.

---

## 8. Fixes Applied (Summary)

| File | Change |
|------|--------|
| `backend/database.py` | Email lookup: `LOWER(TRIM(email))`; username: `TRIM(username)`; `get_user_by_identifier` handles @; added `delete_session_by_token` |
| `backend/main.py` | Register: store email lowercase; added `POST /api/auth/logout`; login: specific error messages + logging |
| `frontend/src/api/client.ts` | Added `authAPI.logout()`; global 401 interceptor (clear session, redirect); store last error in `debug_last_auth_error` |
| `frontend/src/components/AppShell.tsx` | Logout calls `authAPI.logout()` before `clearAuthItems` |
| `frontend/src/pages/Auth.tsx` | Store failed login/register error in `debug_last_auth_error` |
| `frontend/src/pages/DebugAuth.tsx` | New dev-only page at `/debug/auth` showing session status |
| `frontend/src/App.tsx` | Route for `/debug/auth` (dev only) |
| `scripts/check_wizard_integrity.py` | New script to assert no duplicate question IDs |

---

## 9. File Paths Quick Reference

- Auth UI: `frontend/src/pages/Auth.tsx`
- Auth hook: `frontend/src/hooks/useAuth.ts`
- Auth storage: `frontend/src/utils/demo.ts`
- API client: `frontend/src/api/client.ts`
- Backend register/login: `backend/main.py` (register, login, get_current_user)
- DB user/session ops: `backend/database.py`
