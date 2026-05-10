-- Allow EMPLOYEE_UNSUBMIT and HR_REOPEN from HR_REVIEW as well as EMPLOYEE_SUBMITTED.
-- Also look up by case_id when id not found (wizard URL may use case_id).
-- Fixes "Invalid status transition" when case has moved to HR_REVIEW (e.g. HR opened it).

create or replace function public.transition_assignment(
  p_assignment_id text,
  p_action text,
  p_note text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor uuid;
  v_row public.case_assignments%rowtype;
  v_assignment_id text;
  v_now timestamptz;
  v_from text;
  v_to text;
  v_note text;
begin
  v_actor := auth.uid();
  if v_actor is null then
    raise exception 'Not authenticated';
  end if;

  select *
    into v_row
    from public.case_assignments
   where id = p_assignment_id
   for update;

  if not found then
    select *
      into v_row
      from public.case_assignments
     where case_id = p_assignment_id
     for update;
  end if;

  if not found then
    raise exception 'Assignment not found';
  end if;

  v_assignment_id := v_row.id;

  if p_action in ('EMPLOYEE_SUBMIT', 'EMPLOYEE_UNSUBMIT') then
    if v_row.employee_user_id is null or v_row.employee_user_id <> v_actor::text then
      raise exception 'Not authorized';
    end if;
  elsif p_action = 'HR_REOPEN' then
    if v_row.hr_user_id is null or v_row.hr_user_id <> v_actor::text then
      raise exception 'Not authorized';
    end if;
  else
    raise exception 'Invalid action';
  end if;

  v_from := v_row.status;
  v_now := now();
  v_note := nullif(trim(coalesce(p_note, '')), '');

  if p_action = 'EMPLOYEE_SUBMIT' then
    if v_from <> 'DRAFT' then
      raise exception 'Invalid status transition';
    end if;
    v_to := 'EMPLOYEE_SUBMITTED';

    update public.case_assignments
       set status = v_to,
           submitted_at_ts = v_now,
           submitted_at_text = v_now::timestamptz::text,
           updated_at_ts = v_now,
           updated_at_text = v_now::timestamptz::text
     where id = v_assignment_id;
  elsif p_action = 'EMPLOYEE_UNSUBMIT' then
    if v_from not in ('EMPLOYEE_SUBMITTED', 'HR_REVIEW') then
      raise exception 'Invalid status transition';
    end if;
    v_to := 'DRAFT';

    update public.case_assignments
       set status = v_to,
           submitted_at_ts = null,
           submitted_at_text = null,
           updated_at_ts = v_now,
           updated_at_text = v_now::timestamptz::text
     where id = v_assignment_id;
  elsif p_action = 'HR_REOPEN' then
    if v_from not in ('EMPLOYEE_SUBMITTED', 'HR_REVIEW') then
      raise exception 'Invalid status transition';
    end if;
    v_to := 'DRAFT';

    update public.case_assignments
       set status = v_to,
           submitted_at_ts = null,
           submitted_at_text = null,
           updated_at_ts = v_now,
           updated_at_text = v_now::timestamptz::text,
           hr_notes = case when v_note is null then hr_notes else v_note end
     where id = v_assignment_id;
  end if;

  insert into public.assignment_audit_log (
    assignment_id,
    actor_user_id,
    action,
    from_status,
    to_status,
    metadata
  )
  values (
    v_assignment_id,
    v_actor,
    p_action,
    v_from,
    v_to,
    jsonb_build_object('note', v_note, 'at', v_now)
  );

  return jsonb_build_object(
    'success', true,
    'assignment_id', v_assignment_id,
    'from_status', v_from,
    'to_status', v_to
  );
end;
$$;
