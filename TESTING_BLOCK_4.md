# Building Block #4 — Test Checklist

This checklist is the authoritative procedure for validating the assignment transition RPCs and wizard controls.

## A) Setup & instrumentation

### A1 — Identify test entities
Pick a single assignment and record:
- `ASSIGNMENT_ID`
- `CASE_ID`
- `EMPLOYEE_EMAIL` + `EMPLOYEE_USER_ID`
- `HR_EMAIL` + `HR_USER_ID`

Query:
```sql
select id, case_id, employee_user_id, hr_user_id, status
from public.case_assignments
where id = 'ASSIGNMENT_ID';
```

### A2 — Feature flags
- “Fill for test” visible only in dev, or if the logged-in email ends with `@relopass.com`.
- Not visible in prod for non-`@relopass.com` users.

### A3 — DevTools Network
Confirm you can inspect:
- Save/persist calls from wizard steps
- Submit call (transition RPC)
- Unsubmit / Reopen calls (transition RPC)

### A4 — DB snapshot queries
Snapshot:
```sql
select
  id,
  status,
  employee_user_id,
  hr_user_id,
  submitted_at_text,
  updated_at_text,
  submitted_at_ts,
  updated_at_ts,
  hr_notes
from public.case_assignments
where id = 'ASSIGNMENT_ID';
```

Audit:
```sql
select
  created_at,
  action,
  from_status,
  to_status,
  actor_user_id,
  metadata
from public.assignment_audit_log
where assignment_id = 'ASSIGNMENT_ID'
order by created_at desc
limit 20;
```

## B) Employee flow tests

### B1 — Wizard loads persisted values
1) Open `/employee/case/ASSIGNMENT_ID/wizard/1`.
2) Verify fields are populated from DB.
3) Change a field and click **Save as draft & exit**.
4) Reopen the wizard and confirm value persists.

Expected:
- `updated_at_*` changed.
- Saved values present in wizard on reload.

### B2 — Fill for test (DRAFT only)
1) Ensure status = `DRAFT`.
2) Click **Fill for test**.
3) Verify all steps show filled values.
4) Click Save/Next to persist.
5) Refresh and confirm values persist.

Expected:
- Status remains `DRAFT`.
- `submitted_at_*` stays NULL.
- Values are realistic and consistent:
  - future dates
  - valid enums
  - single → no dependents

### B3 — Submit to HR
1) From DRAFT, click **Submit to HR for review**.
2) Confirm UI shows submitted state.
3) Confirm wizard becomes read-only.

Expected DB:
- `status = EMPLOYEE_SUBMITTED`
- `submitted_at_ts` and `submitted_at_text` set
- Audit row: `EMPLOYEE_SUBMIT` with from/to status.

### B4 — Edit responses (employee unsubmit)
1) While status = EMPLOYEE_SUBMITTED, click **Edit responses**.
2) Confirm wizard becomes editable.
3) Modify field, Save, refresh.

Expected DB:
- `status = DRAFT`
- `submitted_at_*` cleared
- Audit row: `EMPLOYEE_UNSUBMIT`.

## C) HR flow tests

### C1 — HR sees submitted case
1) Log in as assigned HR.
2) Open the assignment detail page.
3) Verify answers are visible read-only.

### C2 — HR reopen for employee
1) Click **Reopen for employee**.
2) Enter note (e.g. “Please correct origin city”).
3) Confirm UI shows reopened state.

Expected DB:
- `status = DRAFT`
- `submitted_at_*` cleared
- `hr_notes` updated OR note in audit metadata
- Audit row: `HR_REOPEN`.

## D) DB integrity tests

### D1 — Timestamp consistency
After each transition:
```sql
select
  (submitted_at_ts is null) as ts_null,
  (submitted_at_text is null) as text_null,
  submitted_at_ts,
  submitted_at_text
from public.case_assignments
where id = 'ASSIGNMENT_ID';
```

### D2 — Audit log correctness
Verify each action creates exactly 1 audit row with correct `from_status`, `to_status`, and `actor_user_id`.

### D3 — No-op transitions
Call submit twice. Second call should fail with `Invalid status transition` (or equivalent error).

## E) Authorization tests

### E1 — Wrong employee
Try unsubmit as a different employee. Expect “Not authorized”.

### E2 — Wrong HR
Try HR reopen as a different HR. Expect “Not authorized”.

### E3 — Employee calling HR reopen
Attempt HR_REOPEN as employee. Expect “Not authorized”.

## F) Regression tests

### F1 — Wizard persistence
Save changes → exit → reopen → values present.

### F2 — Dashboard state
- DRAFT shows as incomplete
- EMPLOYEE_SUBMITTED shows as submitted/locked

### F3 — Providers flow
Providers selection and saving still persists and reloads.

## G) Failure-mode tests

### G1 — Network error during submit
Simulate offline. Submit should show error and not change DB.

### G2 — RPC error
Trigger invalid transition. UI should show error and remain consistent.

### G3 — Refresh mid-save
Click save and refresh quickly. Reloaded state should match last persisted values.

## H) Definition of Done
- Fill-for-test works (dev-only), persists valid data.
- Submit / unsubmit / HR reopen transitions work with audit + timestamps.
- Unauthorized transitions blocked.
- No `text = uuid` errors.
- No “success true but status unchanged”.
