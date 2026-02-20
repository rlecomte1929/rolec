# Auth & Demo Fixes Applied

## Concrete Fixes

### Backend

1. **`backend/database.py`**
   - `get_user_by_email`: Case-insensitive lookup via `LOWER(TRIM(email))`
   - `get_user_by_username`: Trim whitespace
   - `get_user_by_identifier`: Try username first, then email; handles `@` for email
   - `delete_session_by_token`: New method to invalidate session on logout

2. **`backend/main.py`**
   - Register: Normalize email to lowercase before duplicate check and storage
   - Login: Clearer error messages ("Invalid username or email", "Incorrect password")
   - Login/Register: Request logging (success/fail with sanitized identifiers)
   - `POST /api/auth/logout`: New endpoint to delete session by token

### Frontend

3. **`frontend/src/api/client.ts`**
   - `authAPI.logout()`: Calls `POST /api/auth/logout` before client clear
   - Global 401 response interceptor: Clears session, saves error to `debug_last_auth_error`, redirects to `/auth?mode=login`
   - Skips 401 handling for login/register endpoints

4. **`frontend/src/components/AppShell.tsx`**
   - Logout button: Calls `authAPI.logout()` then `clearAuthItems()` then redirect

5. **`frontend/src/pages/Auth.tsx`**
   - On login/register failure: Store `err.response?.data?.detail` in `localStorage.debug_last_auth_error`

6. **`frontend/src/pages/DebugAuth.tsx`** (new)
   - Dev-only page at `/debug/auth` showing: session status, token preview, user id, email, username, role, storage type, last auth error

7. **`frontend/src/App.tsx`**
   - Route `/debug/auth` → `DebugAuth` (only when `import.meta.env.DEV`)

### Scripts & Docs

8. **`scripts/check_wizard_integrity.py`** (new)
   - Asserts no duplicate question IDs in question_bank

9. **`docs/AUTH_AND_DATA_FLOW_MAP.md`** (new)
   - Auth stack, flow locations, session storage, DB association, risk areas, root cause analysis

10. **`docs/DEMO_RUNBOOK.md`** (new)
    - 10-step demo checklist, log locations, common issues

---

## New Env Vars

None. Uses existing `VITE_API_URL` for API base.

---

## Demo Checklist (10 Steps)

1. Start backend (uvicorn)
2. Start frontend (npm run dev)
3. Test connection on landing
4. Create demo user (register)
5. Verify login (logout, login again)
6. Return visit (close tab, reopen — session persists)
7. Employee flow (claim assignment, complete wizard)
8. HR flow (create case, assign, review)
9. Debug auth (`/debug/auth` in dev)
10. Reset demo data (Reset test data button or DB reset)
