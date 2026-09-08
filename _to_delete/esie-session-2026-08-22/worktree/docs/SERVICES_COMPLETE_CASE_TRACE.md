# Services "Complete your case first" – Trace & Fixes

## 1. Guard Logic

**Where:** `frontend/src/pages/ProvidersPage.tsx` lines 174–183

```tsx
if (!assignmentId) {
  return (
    <AppShell ...>
      <Alert variant="info">Complete your case first to unlock services selection.</Alert>
      <Button onClick={() => navigate(buildRoute('employeeDashboard'))}>Back to Dashboard</Button>
    </AppShell>
  );
}
```

**Condition:** The Services page blocks when `assignmentId` is `null`.

---

## 2. Where `assignmentId` Comes From

**Source:** `useEmployeeAssignment()` from `frontend/src/contexts/EmployeeAssignmentContext.tsx`

**Effect:**
- Runs only if: `isEmployee` (role === 'EMPLOYEE' | 'ADMIN') **and** `getAuthItem('relopass_token')` exists
- Calls `employeeAPI.getCurrentAssignment()` → `GET /api/employee/assignments/current`
- Sets `assignmentId` only if `res?.assignment?.id` is truthy
- On any error (e.g. 401): `setAssignmentId(null)`

So the message means “no assignment yet”, not “intake wizard incomplete”.

---

## 3. Backend: `GET /api/employee/assignments/current`

**File:** `backend/main.py` ~line 1836

**Logic:**
1. `db.get_assignment_for_employee(effective["id"])` – assignment with `employee_user_id = user.id`
2. If none: `db.get_unassigned_assignment_by_identifier(username_or_email)` – unclaimed assignment for this identifier
3. If found (and not impersonation): auto-claim, then return that assignment
4. Otherwise: `return {"assignment": None}`

**Assignment is null when:**
- No row in `case_assignments` with `employee_user_id = user.id`
- No unassigned assignment matching the user’s identifier

---

## 4. Why It Fails After Completing the Intake Wizard

Possible causes:

| # | Cause | Explanation |
|---|-------|-------------|
| 1 | **401 / API error** | Token expired or invalid → `.catch()` → `setAssignmentId(null)` |
| 2 | **`res.assignment` is null** | Backend returns `{ assignment: null }` – no assignment linked to the employee |
| 3 | **Effect never ran** | No `relopass_token` or `!isEmployee` → `assignmentId` never set |
| 4 | **Cache + timing** | `getCurrentAssignment` is cached 30s; after expiry, next call can fail and set null |

---

## 5. Token 400

`POST token?grant_type=password` 400 is typically from Supabase auth.

- ReloPass uses `relopass_token` (login via backend `/api/auth/login`)
- If you see “test15 EMPLOYEE”, you are logged in with ReloPass
- Token 400 is likely a separate OAuth/Supabase flow (e.g. refresh or legacy integration) and usually unrelated to `assignmentId`

---

## 6. Suggested Fixes

### A. Clearer Copy

The current text is misleading because the guard is “no assignment”, not “wizard incomplete”:

```
Complete your case first to unlock services selection.
```

Better options:

- “You need an active assignment to use Services. Claim an assignment from your invite or return to Dashboard.”
- “No assignment found. Please claim your assignment or contact HR.”

### B. Refetch on Visibility / Return

Refetch when the user returns to the Services page so a transient 401 doesn’t permanently block them:

- Use `visibilitychange` or route change to invalidate cache and call `getCurrentAssignment` again
- Or: add a “Retry” button on the blocked state that refetches assignment

### C. Invalidate Cache on 401

On 401, clear the `employee:current-assignment` cache so the next call uses a fresh token instead of stale data.

### D. Distinguish “No Assignment” vs “API Error”

- If `GET /api/employee/assignments/current` fails (e.g. 401): show “Session may have expired. Please log in again.”
- If it succeeds with `{ assignment: null }`: show “No assignment found. Claim an assignment or contact HR.”

---

## 7. Quick Checks

1. **Network tab:** Inspect `GET /api/employee/assignments/current` – status and response
2. **Console:** Any 401 handling / auth errors
3. **Application → Local Storage:** `relopass_token` and `relopass_role` present?
4. **Backend:** Ensure `case_assignments` has a row with `employee_user_id` = your user id for the claimed assignment
