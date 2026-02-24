-- Assignment verification RPCs for dev/admin
-- Confirm case_assignments exists and is visible under RLS per role

-- Enable RLS on case_assignments so get_assignment_by_id verifies per-role visibility
alter table if exists public.case_assignments enable row level security;

drop policy if exists assignment_verify_employee_select on public.case_assignments;
drop policy if exists assignment_verify_hr_select on public.case_assignments;

create policy assignment_verify_employee_select
  on public.case_assignments for select to authenticated
  using (
    employee_user_id is not null
    and (employee_user_id::uuid = auth.uid() or employee_user_id = auth.uid()::text)
  );

create policy assignment_verify_hr_select
  on public.case_assignments for select to authenticated
  using (
    hr_user_id is not null
    and (hr_user_id::uuid = auth.uid() or hr_user_id = auth.uid()::text)
  );

-- Optional: dev view for admins (service_role only - revoke from anon/authenticated)
create or replace view public.dev_case_assignments_view as
select
  id as assignment_id,
  case_id,
  employee_user_id,
  hr_user_id,
  status,
  created_at,
  updated_at
from public.case_assignments;

revoke all on public.dev_case_assignments_view from anon;
revoke all on public.dev_case_assignments_view from authenticated;
grant select on public.dev_case_assignments_view to service_role;

comment on view public.dev_case_assignments_view is 'Dev/admin only: inspect assignments. Use service_role.';

-- RPC 1: get_assignment_by_id - SECURITY INVOKER (respects RLS)
-- Returns row if visible to current user, else found=false
create or replace function public.get_assignment_by_id(p_assignment_id text)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_row record;
begin
  if auth.uid() is null then
    return jsonb_build_object('found', false, 'error', 'Not authenticated');
  end if;

  select id, case_id, employee_user_id, hr_user_id, status, created_at, updated_at
  into v_row
  from public.case_assignments
  where id = p_assignment_id
  limit 1;

  if not found then
    return jsonb_build_object('found', false);
  end if;

  return jsonb_build_object(
    'found', true,
    'row', jsonb_build_object(
      'id', v_row.id,
      'case_id', v_row.case_id,
      'employee_user_id', v_row.employee_user_id,
      'hr_user_id', v_row.hr_user_id,
      'status', v_row.status,
      'created_at', v_row.created_at,
      'updated_at', v_row.updated_at
    )
  );
end;
$$;

grant execute on function public.get_assignment_by_id(text) to authenticated;
comment on function public.get_assignment_by_id is 'Returns assignment row if visible to current user (RLS). For verification.';

-- RPC 2: assert_assignment_links - SECURITY DEFINER, safe (caller must be employee or HR)
-- Verifies assignment links match expected; only executable by expected_employee or expected_hr
create or replace function public.assert_assignment_links(
  p_assignment_id text,
  p_expected_employee uuid,
  p_expected_hr uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor uuid;
  v_row record;
  v_emp_match boolean;
  v_hr_match boolean;
begin
  v_actor := auth.uid();
  if v_actor is null then
    return jsonb_build_object('found', false, 'error', 'Not authenticated');
  end if;

  -- Only allow if caller is the expected employee or expected HR
  if v_actor <> p_expected_employee and v_actor <> p_expected_hr then
    return jsonb_build_object(
      'found', false,
      'error', 'Not authorized: caller must be the expected employee or HR'
    );
  end if;

  select employee_user_id, hr_user_id into v_row
  from public.case_assignments
  where id = p_assignment_id
  limit 1;

  if not found then
    return jsonb_build_object('found', false);
  end if;

  v_emp_match := (v_row.employee_user_id::uuid = p_expected_employee or v_row.employee_user_id = p_expected_employee::text);
  v_hr_match := (v_row.hr_user_id::uuid = p_expected_hr or v_row.hr_user_id = p_expected_hr::text);

  return jsonb_build_object(
    'found', true,
    'matches_employee', coalesce(v_emp_match, false),
    'matches_hr', coalesce(v_hr_match, false),
    'employee_user_id', v_row.employee_user_id,
    'hr_user_id', v_row.hr_user_id
  );
end;
$$;

grant execute on function public.assert_assignment_links(text, uuid, uuid) to authenticated;
comment on function public.assert_assignment_links is 'Verify assignment links. Caller must be expected_employee or expected_hr.';
