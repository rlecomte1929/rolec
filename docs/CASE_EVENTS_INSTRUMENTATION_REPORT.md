# Case Events Instrumentation Report

## 1. Exact Live Path (HR Approve/Reject)

| Layer | Component | Details |
|-------|-----------|---------|
| **Frontend** | `HrCaseSummary.tsx` | `handleApprove()` / `handleRequestChanges()` (reject) |
| **Button** | "Approve case" / "Request changes" in decision modal |
| **API Client** | `hrAPI.decide(assignment.id, 'approved' \| 'rejected', opts)` |
| **HTTP** | `POST /api/hr/assignments/{assignmentId}/decision` |
| **Backend Route** | `main.py` → `hr_decision()` |
| **DB Writes** | `db.set_assignment_decision()` then `db.insert_case_event()` |

**Note:** `HrAssignmentReview` shows assignment status but does not contain approve/reject buttons in the reviewed code. The live HR decision flow uses **HrCaseSummary** (`/hr/cases/:caseId`).

---

## 2. All Instrumented Paths

| Flow | Frontend | API | Backend Route | Event Type |
|------|----------|-----|---------------|------------|
| **Approve** | HrCaseSummary | hrAPI.decide(id, 'approved') | POST /api/hr/assignments/{id}/decision | assignment.approved |
| **Reject** | HrCaseSummary | hrAPI.decide(id, 'rejected') | POST /api/hr/assignments/{id}/decision | assignment.rejected |
| **Employee submit** | (employee flow) | employeeAPI.submitAssignment(id) | POST /api/employee/assignments/{id}/submit | assignment.submitted |
| **Claim (auto)** | GET /employee/assignments/current | (no explicit call) | GET /api/employee/assignments/current | assignment.claimed |
| **Claim (explicit)** | Claim flow | POST claim | POST /api/employee/assignments/{id}/claim | assignment.claimed |
| **Assign** | HrDashboard handleAssign | hrAPI.assignCase() | POST /api/hr/cases/{caseId}/assign | assignment.created |

---

## 3. Why Events Were Not Produced (Root Cause Analysis)

**Most likely cause: Supabase RLS policy mismatch**

The migration `20260321000000_case_events_phase1.sql` replaced the insert policy:

- **Old:** `case_events_hr_insert` — insert allowed when `ca.hr_user_id = auth.uid()::text` (HR owns the case).
- **New:** `case_events_insert_self` — insert allowed only when `actor_principal_id = auth.uid()::text`.

The backend uses **SQLAlchemy with DATABASE_URL** (direct Postgres connection), not Supabase Auth JWT. So:

- `auth.uid()` in RLS = the Postgres session role (e.g. `postgres` or pooler user), or `NULL`.
- `actor_principal_id` = our app user ID (from `users` table).

These never match → RLS silently rejects the insert. Manual inserts may work if run with a different connection or with RLS bypass.

**Other possibilities:**
- Migration `20260321000000` not applied in production.
- `case_events` table missing or schema mismatch (e.g. `payload` or `actor_principal_id` columns absent).

---

## 4. Structured Logs Added

Each instrumented path now logs:

| Log key | When |
|---------|------|
| `approval_flow_entered` | Start of hr_decision |
| `approval_flow` | assignment_id, case_id, decision |
| `before_set_assignment_decision` | Before DB update |
| `after_set_assignment_decision` | After DB update |
| `before_insert_case_event` | Before event insert |
| `after_insert_case_event` | After successful insert |
| `event_insert_error` | On insert failure (assignment_id, case_id, event_type, error, exc_info) |

Similar patterns for: `employee_submit_flow_entered`, `claim_flow_entered`, `assign_flow`.

---

## 5. Files Changed

| File | Changes |
|------|---------|
| `backend/main.py` | Structured logging + try/except around `insert_case_event` in: `hr_decision`, `submit_assignment`, `claim_assignment`, `get_assignment_for_employee` (auto-claim), `assign_case` (assignment.created). On error: log `event_insert_error` and re-raise. |

---

## 6. Manual Verification Steps (Render Logs)

1. **Deploy** the instrumented backend to Render.

2. **HR Approve:**
   - Open HrCaseSummary for a submitted assignment.
   - Click "Approve case".
   - In Render logs, search for:
     - `approval_flow_entered`
     - `before_set_assignment_decision`
     - `after_set_assignment_decision`
     - `before_insert_case_event`
     - Either `after_insert_case_event` (success) or `event_insert_error` (failure).

3. **HR Reject:**
   - Click "Request changes" instead.
   - Same log sequence with `decision=rejected`.

4. **Employee submit:**
   - Submit an assignment from the employee wizard.
   - Search for `employee_submit_flow_entered`, `before_insert_case_event`, `after_insert_case_event` or `event_insert_error`.

5. **Claim:**
   - Employee logs in and claims (or auto-claim via GET /assignments/current).
   - Search for `claim_flow_entered`, `before_insert_case_event`, etc.

6. **If `event_insert_error` appears:**
   - Note `assignment_id`, `case_id`, `event_type`, and the full error message.
   - Likely causes: RLS policy, missing column, or permission issue.

---

## 7. Recommended Fix for RLS

If logs show `event_insert_error` with an RLS/permission-style error:

1. **Option A:** Revert the insert policy to allow backend service role:

   ```sql
   drop policy if exists case_events_insert_self on public.case_events;
   create policy case_events_service_insert on public.case_events for insert
     to service_role
     with check (true);
   -- or use a backend role that bypasses RLS
   ```

2. **Option B:** Use `SET LOCAL` in the backend to pass `request.jwt.claims.sub` (or similar) so RLS can validate `actor_principal_id` against it.

3. **Option C:** Ensure the backend connects with a role that bypasses RLS (e.g. `postgres` superuser or `service_role`), if acceptable for your security model.
