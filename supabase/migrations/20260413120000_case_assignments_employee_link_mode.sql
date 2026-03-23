-- Tracks explicit pending-claim vs legacy auto-reconcile behavior for HR-created assignments.
-- Application INSERT always supplies this column (see backend/database.py create_assignment).
alter table public.case_assignments
  add column if not exists employee_link_mode text;

create index if not exists idx_case_assignments_employee_link_mode
  on public.case_assignments (employee_link_mode)
  where employee_user_id is null and employee_link_mode is not null;
