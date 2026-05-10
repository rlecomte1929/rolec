# Block 5: HR Review + Feedback – Testing Checklist

## Checkpoint 1: Migration applied

### Run migration
```bash
# Option A: Supabase CLI (local)
npx supabase db push

# Option B: Run SQL directly in Supabase Dashboard → SQL Editor
# Copy contents of: supabase/migrations/20260223120000_case_feedback.sql
```

### Verify
```sql
-- Table exists
SELECT * FROM public.case_feedback LIMIT 0;

-- RLS enabled
SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'case_feedback';
-- relrowsecurity should be true
```

**Stop point**: Confirm table exists and RLS is enabled before continuing.

---

## Checkpoint 2: HR Review dashboard loads

1. Log in as HR user (e.g. `hr@relopass.com` via Switch User or Auth).
2. Ensure `VITE_SUPABASE_ACCESS_TOKEN` in `frontend/.env.development` is set to a valid HR JWT.
3. Open **http://localhost:3004/hr/review** (or your dev port).
4. You should see:
   - "No assigned cases" if none exist, OR
   - A list of assigned cases with Open buttons.

**Stop point**: Confirm the list loads (or shows "No assigned cases" correctly).

---

## Checkpoint 3: HR can post feedback

1. From Review dashboard, click **Open** on a case (or go directly to `/hr/review/case/{caseId}`).
2. You should see:
   - Read-only summary of wizard data (Relocation Basics, Employee Profile, etc.)
   - Feedback panel with section dropdown, text area, "Send feedback" button.
3. Select a section, type a message, click **Send feedback**.
4. Feedback should appear immediately in "Previous feedback" list.

### Confirm in DB
```sql
SELECT id, case_id, assignment_id, section, message, created_at_ts 
FROM public.case_feedback 
ORDER BY created_at_ts DESC LIMIT 5;
```

**Stop point**: Confirm feedback persists and shows in UI.

---

## Checkpoint 4: Employee can see feedback

1. Log in as the employee assigned to that case (e.g. `test6@relopass.com`).
2. Ensure `VITE_SUPABASE_ACCESS_TOKEN` is the **employee** JWT (switch token in `.env.development` if needed).
3. Go to **My Case** (wizard): `/employee/case/{assignmentId}/wizard/1`.
4. You should see an **HR Feedback** panel with the feedback entries (grouped, newest first).

**Stop point**: Confirm employee sees the same feedback.

---

## Troubleshooting

| Issue | Possible cause |
|-------|----------------|
| "Not authenticated" / token errors | Set `VITE_SUPABASE_ACCESS_TOKEN` with valid JWT for the role you're testing. Restart Vite after changing `.env`. |
| "No assigned cases" (but cases exist) | `case_assignments.hr_user_id` must match the JWT `sub`. Ensure you're logged in as the HR user who owns the assignment. |
| "Not authorized to view this case" | RLS: assignment must have `hr_user_id` = auth.uid() for HR, or `employee_user_id` = auth.uid() for employee. |
| Feedback insert fails | Check RLS policy `hr_insert_feedback` – assignment must exist and `hr_user_id` must match. |
