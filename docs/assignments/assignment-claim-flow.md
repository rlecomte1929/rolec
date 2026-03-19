# Assignment Claim Flow

**Date:** 2025-03-19  
**Purpose:** Document the employee claim/connect flow from invitation to case access. Covers both existing-account and new-account scenarios.

---

## Before Flow (Observed Behavior)

1. HR creates assignment with employee email/username.
2. Assignment stored with `employee_user_id` (if user exists) or null, and `employee_identifier` (required).
3. Employee receives assignment ID (from notification or shared link).
4. Employee signs in (existing account) or registers (new account).
5. Employee navigates to claim flow, enters assignment ID and email.
6. `POST /api/employee/assignments/{assignment_id}/claim` with `{ email }`.

---

## Problems Found

### 1. Identifier matching sensitivity

- Matching is case-insensitive (lowercased).
- Both email and username are checked.
- If HR used "Jane@Company.com" and employee registers with "jane@company.com", match works.

### 2. No explicit company check on claim

- Claim validates identity via `employee_identifier` match only.
- Cross-company scenario: two employees in different companies with same email is rare; identifier is the intended binding.
- No change needed; identity match is sufficient.

### 3. Auto-claim on dashboard

- `get_employee_dashboard` and `get_employee_assignment` auto-attach when `get_unassigned_assignment_by_identifier` finds a match.
- This can race with explicit claim; both paths call `attach_employee_to_assignment`.
- Attach is idempotent (UPDATE sets employee_user_id); no duplicate records.

### 4. mark_invites_claimed by identifier only

- `mark_invites_claimed(employee_identifier)` updates all invites with that identifier.
- Multiple assignments for same person would all be marked claimed.
- Acceptable; identifier is the person-level key.

---

## Final Corrected Flow

### Assignment Creation (HR or Admin)

1. Assignment created with:
   - `company_id` on case (from HR company or admin body)
   - `employee_user_id` = profile id if user exists, else null
   - `employee_identifier` = email or username (required)
2. Optional: `create_assignment_invite` with token; message includes assignment ID.

### Employee With Existing Account

1. Employee logs in.
2. **Path A — Dashboard:** `GET /api/employee/dashboard` or `GET /api/employee/assignments/current`:
   - `get_assignment_for_employee(user_id)` finds assignment → return it.
   - Else `get_unassigned_assignment_by_identifier(email_or_username)`:
     - If found: `attach_employee_to_assignment`, then return assignment.
3. **Path B — Explicit claim:** Employee has assignment ID, opens claim form:
   - `POST /api/employee/assignments/{id}/claim` with `{ email }`
   - Validates: request email matches logged-in user; assignment.employee_identifier matches user.
   - `attach_employee_to_assignment`, `mark_invites_claimed`, `ensure_case_participant`, `insert_case_event`.

### Employee Without Account

1. Employee receives assignment ID (and optionally invite token).
2. Employee registers with same email used by HR.
3. After registration, employee logs in.
4. Same as "existing account" — dashboard or explicit claim connects the assignment.

### Deterministic Matching Rules

| Match Key | Normalization |
|-----------|---------------|
| employee_identifier | `strip().lower()` |
| user email/username | `[x.lower() for x in [email, username] if x]` |
| Request body email | `strip().lower()` |

### Idempotency

- `attach_employee_to_assignment` is an UPDATE; re-calling with same user_id is safe.
- Claim returns success if already linked: `if emp_uid_str == effective_id: return {"success": True}`.
- No duplicate employee or case records created on claim.

---

## Edge Cases Handled

| Case | Behavior |
|------|----------|
| Already claimed by this user | Success; no-op |
| Claimed by different user, same identifier | Treated as "same person" (e.g. profile id vs user id); attach current user |
| Assignment not found | 404 |
| Identifier mismatch | 403 "This assignment was created for a different employee" |
| Request email doesn't match logged-in user | 403 "The identifier you entered does not match your account" |
| New user, no assignment yet | Dashboard shows "Complete your case wizard"; claim form available |
| Impersonation | _deny_if_impersonating blocks claim |

---

## References

- `backend/main.py`: claim_assignment, get_employee_assignment, get_employee_dashboard
- `backend/database.py`: attach_employee_to_assignment, get_assignment_for_employee, get_unassigned_assignment_by_identifier, mark_invites_claimed
- `frontend/src/pages/EmployeeJourney.tsx`: claim form
