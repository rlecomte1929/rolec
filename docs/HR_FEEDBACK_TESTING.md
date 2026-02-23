# HR Feedback on Employee Case – Testing Guide

## Data storage

Feedback is stored in the **backend database** (`hr_feedback` table). The backend creates this table on init. No Supabase migration is required for the feedback feature to work with backend auth.

(Optional: For Supabase-based feedback, run `supabase/migrations/20260224000000_hr_feedback.sql` in Supabase. The app currently uses the backend API.)

## Prerequisites

- HR and Employee users logged in via the ReloPass backend (standard login flow).
- Backend running with database initialized.

## UI flow

### HR side

1. Log in as `hrmanager` / `hr@relopass.com` (or your HR user).
2. Go to **HR Dashboard** or **Employee Dashboard**.
3. Open a case via **Switch Case** or the default selection.
4. In the right sidebar, find the **Provide feedback** card.
5. Type a message (e.g. “Please correct passport expiry date”).
6. Click **Send feedback**.
7. The message appears under **Feedback history** with a timestamp.

### Employee side

1. Log in as `test6@relopass.com` (or the employee assigned to that case).
2. Click **My Case** in the nav.
3. On the **My Case** summary page, find the **Feedback from HR** panel on the right.
4. The HR message should be visible with a timestamp.
5. Click **Continue editing** to open the wizard.
6. On any step, the **HR Feedback** card in the sidebar shows the same messages.
7. Edit a field and click **Save**.
8. Confirm the feedback list is unchanged (no overwrites).

### HR verification after employee save

1. As HR, refresh the Employee Dashboard case view.
2. Employee data should reflect the latest edits.
3. **Feedback history** should still list all prior messages (append-only).

## Acceptance checks

| # | Test | Expected |
|---|------|----------|
| 1 | HR posts feedback | RPC succeeds; new message at top of history |
| 2 | Employee opens My Case | Feedback panel shows the message |
| 3 | Employee edits and saves | Wizard data updates; feedback untouched |
| 4 | HR refreshes case | Employee data updated; feedback history unchanged |
| 5 | Different HR not assigned | Cannot read/insert feedback (0 rows or 403) |
| 6 | Employee tries to insert | Cannot insert (403 via RPC) |
| 7 | UPDATE/DELETE on hr_feedback | 403 (append-only) |
