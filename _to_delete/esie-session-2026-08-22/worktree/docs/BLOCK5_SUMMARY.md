# Block 5: HR Review + Feedback – Implementation Summary

## Files changed / added

### Database
- `supabase/migrations/20260223120000_case_feedback.sql` – new `case_feedback` table, indexes, RLS policies

### API
- `frontend/src/api/feedback.ts` – `listFeedback`, `insertFeedback`, `FEEDBACK_SECTIONS`, types
- `frontend/src/api/review.ts` – `listAssignedCasesForReview`, `getWizardCaseForReview`, `getAssignmentIdForCase`, `getEmployeeAssignmentId`

### Pages
- `frontend/src/pages/HrReviewDashboard.tsx` – assigned cases list (Supabase)
- `frontend/src/pages/HrCaseReview.tsx` – read-only case summary + feedback panel

### Modified
- `frontend/src/navigation/routes.ts` – added `hrReview`, `hrReviewCase`
- `frontend/src/App.tsx` – routes for HrReviewDashboard, HrCaseReview
- `frontend/src/components/AppShell.tsx` – nav link "Review" for HR
- `frontend/src/pages/employee/CaseWizardPage.tsx` – HR Feedback panel

### Docs
- `docs/BLOCK5_AUTH_AND_ROLE.md` – role sourcing
- `docs/BLOCK5_TESTING.md` – testing checklist and checkpoints

---

## Manual test steps

### 1. Apply migration
```bash
npx supabase db push
# OR paste migration SQL in Supabase Dashboard → SQL Editor
```
Wait ~1 min for PostgREST schema cache.

### 2. Set HR token
In `frontend/.env.development`, set `VITE_SUPABASE_ACCESS_TOKEN` to a valid JWT for an HR user who has assigned cases in `case_assignments`. Restart Vite.

### 3. HR flow
- Open http://localhost:3004/hr/review
- You should see assigned cases (or "No assigned cases")
- Click Open → read-only summary + feedback panel
- Add feedback, send → it should appear immediately

### 4. Employee flow
- Set `VITE_SUPABASE_ACCESS_TOKEN` to employee JWT
- Restart Vite, open My Case wizard
- HR Feedback panel should show feedback for that case

---

## Data flow

- **HR list**: `case_assignments` (hr_user_id = auth.uid()) + `wizard_cases` (by case_id)
- **HR case**: `wizard_cases` (by id) for draft, `getAssignmentIdForCase` for assignment
- **Feedback**: `case_feedback` with RLS (HR insert/select for own assignments, Employee select for own)
- **Employee**: `getEmployeeAssignmentId` (id or case_id) → `listFeedback(assignmentId)`
