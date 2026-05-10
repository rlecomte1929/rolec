# Assignment Debug – RLS Verification

Verify that `case_assignments` exists in Supabase and is visible under RLS per role.

## 1. Apply the migration

Run `supabase/migrations/20260225000000_assignment_debug_rpcs.sql` in the Supabase SQL Editor.

This migration:

- Enables RLS on `case_assignments`
- Adds policies so employees see their assignments and HR sees their own
- Creates `dev_case_assignments_view` (service_role only)
- Adds RPCs: `get_assignment_by_id`, `assert_assignment_links`

## 2. Seed an assignment (if needed)

If no assignment row exists, create one. Replace UUIDs with real Supabase auth user IDs.

```sql
-- Get your user IDs from auth.users:
-- SELECT id, email FROM auth.users;

INSERT INTO public.case_assignments (
  id,
  case_id,
  hr_user_id,
  employee_user_id,
  employee_identifier,
  status,
  created_at,
  updated_at
) VALUES (
  '284a54cb-f6ca-4154-beac-09f014618000',  -- assignment id
  '284a54cb-f6ca-4154-beac-09f014618000',  -- case_id (can match)
  'e9901a18-47e3-4e4b-86ed-d58719277f17',  -- hr_user_id (HR auth.users.id)
  'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',   -- employee_user_id (Employee auth.users.id)
  'employee@example.com',
  'DRAFT',
  now()::text,
  now()::text
);
```

Use the Supabase Dashboard or `service_role` to run this (RLS may block regular users).

## 3. Test with the debug panel

1. Start the frontend in dev: `npm run dev`
2. Sign in with **ReloPass** (employee or HR). The panel uses backend auth (`relopass_token`) first, so no Supabase JWT is needed.
3. Go to **My Case** as the employee or **Employee Dashboard** as HR
4. The **Assignment debug** panel appears (dev only)
5. Assignment ID is prefilled from the route
6. Click **Check as current user**

> **Note:** The panel tries the backend `/api/debug/assignment-check` first (uses `relopass_token`). If that fails, it falls back to Supabase RPC (requires Supabase session).

### Expected results

| User             | Expected                                           |
|------------------|----------------------------------------------------|
| Employee (owner) | `found: true`, `employee_user_id` matches `auth.uid()` |
| HR (owner)       | `found: true`, `hr_user_id` matches `auth.uid()`      |
| Random user      | `found: false` or error                             |

## 4. RPCs

### `get_assignment_by_id(p_assignment_id text)`

- **Security**: INVOKER (honors RLS)
- Returns `{ found: boolean, row?: {...} }` if visible
- Returns `{ found: false }` if not found or blocked by RLS

### `assert_assignment_links(p_assignment_id, p_expected_employee, p_expected_hr)`

- **Security**: DEFINER, but caller must be `expected_employee` or `expected_hr`
- Verifies assignment links without exposing data to others

## 5. Dev view

`dev_case_assignments_view` is restricted to `service_role`. Use it in the SQL Editor or with a service-role client.

## 6. SQL notes

- **UUID literals must be quoted** in SQL: `WHERE case_id = '0531217e-ff02-4a9e-9b43-f3553d5ea9b0'`. Unquoted UUIDs cause "trailing junk after numeric literal" errors.
