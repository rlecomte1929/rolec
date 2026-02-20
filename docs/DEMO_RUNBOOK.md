# ReloPass Demo Runbook

## 10-Step Demo Checklist (Before Client Call)

1. **Start backend** (if local)
   ```bash
   cd backend && uvicorn main:app --reload --host 0.0.0.0
   ```

2. **Start frontend** (if local)
   ```bash
   cd frontend && npm run dev
   ```

3. **Test connection** — On landing page, click "Test connection". Should show "Connected" with latency.

4. **Create demo user**
   - Go to `/auth?mode=register`
   - Fill: Full name, Username (e.g. `demouser`), Email (e.g. `demo@relopass.com`), Password, Role (Employee or HR)
   - Click "Create Account"
   - Should redirect to Employee Journey or HR Dashboard

5. **Verify login**
   - Click Logout (top right)
   - Go to `/auth?mode=login`
   - Enter same username or email + password
   - Click "Sign In"
   - Should sign in successfully

6. **Return visit (session persistence)**
   - While logged in, close the browser tab
   - Reopen and go to `relopass.com` (or localhost)
   - Session persists (token in localStorage) — you should still be logged in
   - If not, login again — data should load

7. **Employee flow (if Employee role)**
   - HR must create a case and assign to this employee first
   - Or use "Claim assignment" with assignment ID from HR
   - Complete wizard steps 1–5
   - Submit to HR

8. **HR flow (if HR role)**
   - Create case (button on dashboard)
   - Assign to employee (enter their email or username)
   - Copy Assignment ID, share with employee
   - View Case Summary, run compliance, approve/request changes

9. **Debug auth (dev only)**
   - Visit `/debug/auth` to see session status, user id, last auth error

10. **Reset demo data (if needed)**
    - Click "Reset test data" on Auth page (clears localStorage)
    - For DB reset: depends on deployment (SQLite = delete file; Postgres = run migration/reset script)

---

## Where to Check Logs

- **Backend**: Console output from uvicorn. Look for `auth_login`, `auth_register`, `auth_logout`.
- **Frontend**: Browser DevTools → Network tab for failed requests; Console for JS errors.
- **Last auth error**: Stored in `localStorage.debug_last_auth_error` after failed login/register.

---

## Common Issues

| Issue | Check | Fix |
|-------|-------|-----|
| "Invalid credentials" | Wrong password? Email/username typo? | Re-enter; use exact email or username from registration |
| "Email already in use" | Duplicate registration | Use different email or login with existing |
| 401 on protected route | Token expired or invalid | Logout, login again |
| CORS error | API base URL wrong | Set `VITE_API_URL` in frontend `.env` to backend URL |
