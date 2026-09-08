-- Migration: employee_tasks and quote_requests
-- Created: 2026-05-13  (AIQ-34-C)
--
-- NOTE: The employee_tasks table pre-existed with column name 'type' and
-- different status values. This migration idempotently creates or alters it.

-- 1. Create employee_tasks if it does not exist
CREATE TABLE IF NOT EXISTS public.employee_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id text NOT NULL,
  employee_id text NOT NULL,
  org_id text NOT NULL DEFAULT '',
  task_type text NOT NULL DEFAULT 'custom',
  title text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','submitted','revision_requested','approved')),
  due_date date,
  required_file_upload boolean NOT NULL DEFAULT false,
  file_url text,
  submission_data jsonb,
  review_note text,
  submitted_at timestamptz,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 2. If table pre-existed with 'type' column, rename it (safe to run if already renamed)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'employee_tasks' AND column_name = 'type'
  ) THEN
    ALTER TABLE public.employee_tasks RENAME COLUMN "type" TO task_type;
  END IF;
END$$;

-- 3. Fix status constraint to match API expectations
ALTER TABLE public.employee_tasks DROP CONSTRAINT IF EXISTS employee_tasks_status_check;
ALTER TABLE public.employee_tasks
  ADD CONSTRAINT employee_tasks_status_check
  CHECK (status IN ('pending','submitted','revision_requested','approved'));

CREATE INDEX IF NOT EXISTS idx_employee_tasks_case_id ON public.employee_tasks(case_id);
CREATE INDEX IF NOT EXISTS idx_employee_tasks_employee_id ON public.employee_tasks(employee_id);

-- 4. quote_requests
CREATE TABLE IF NOT EXISTS public.quote_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id text NOT NULL,
  employee_id text NOT NULL,
  company_id text NOT NULL DEFAULT '',
  service_categories text[] NOT NULL DEFAULT '{}',
  notes text,
  budget_range text,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','acknowledged','fulfilled')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quote_requests_case_id ON public.quote_requests(case_id);

-- 5. Fix broken trigger function: date - date returns int, not interval
CREATE OR REPLACE FUNCTION public.recalculate_case_risk(p_assignment_id text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_risk text := 'green';
  v_any_overdue boolean := false;
  v_overdue_days int := 0;
  v_budget_limit numeric;
  v_budget_estimated numeric;
  v_prev_risk text;
begin
  select risk_status, budget_limit, budget_estimated
  into v_prev_risk, v_budget_limit, v_budget_estimated
  from public.case_assignments
  where id = p_assignment_id;

  if not found then
    return;
  end if;

  select exists (
    select 1 from public.relocation_tasks
    where assignment_id = p_assignment_id and status = 'overdue'
  ) into v_any_overdue;

  if v_any_overdue then
    select coalesce(max((current_date - due_date)::int), 0) into v_overdue_days
    from public.relocation_tasks
    where assignment_id = p_assignment_id and status = 'overdue' and due_date is not null;
  end if;

  if v_budget_limit is not null and v_budget_estimated is not null and v_budget_estimated > v_budget_limit then
    v_risk := 'red';
  elsif v_overdue_days > 7 then
    v_risk := 'red';
  elsif v_any_overdue then
    v_risk := 'yellow';
  end if;

  update public.case_assignments set risk_status = v_risk where id = p_assignment_id;

  if v_prev_risk is distinct from v_risk and v_risk in ('yellow','red') then
    perform public.notify_hr_risk_change(p_assignment_id, v_risk);
  end if;
end;
$function$;
