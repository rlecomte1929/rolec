-- Add employee first/last name to case_assignments for HR-entered assignment data
alter table if exists public.case_assignments
  add column if not exists employee_first_name text,
  add column if not exists employee_last_name text;
