-- Canonical assignment transition RPC + timestamp sync (additive).

alter table if exists public.case_assignments
  add column if not exists created_at_ts timestamptz,
  add column if not exists updated_at_ts timestamptz,
  add column if not exists submitted_at_ts timestamptz;

update public.case_assignments
  set created_at_ts = nullif(created_at_text, '')::timestamptz
where created_at_ts is null
  and created_at_text is not null
  and created_at_text <> '';

update public.case_assignments
  set updated_at_ts = nullif(updated_at_text, '')::timestamptz
where updated_at_ts is null
  and updated_at_text is not null
  and updated_at_text <> '';

update public.case_assignments
  set submitted_at_ts = nullif(submitted_at_text, '')::timestamptz
where submitted_at_ts is null
  and submitted_at_text is not null
  and submitted_at_text <> '';

update public.case_assignments
  set created_at_text = created_at_ts::timestamptz::text
where (created_at_text is null or created_at_text = '')
  and created_at_ts is not null;

update public.case_assignments
  set updated_at_text = updated_at_ts::timestamptz::text
where (updated_at_text is null or updated_at_text = '')
  and updated_at_ts is not null;

update public.case_assignments
  set submitted_at_text = submitted_at_ts::timestamptz::text
where (submitted_at_text is null or submitted_at_text = '')
  and submitted_at_ts is not null;

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
    raise exception 'Assignment not found';
  end if;

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
     where id = p_assignment_id;
  elsif p_action = 'EMPLOYEE_UNSUBMIT' then
    if v_from <> 'EMPLOYEE_SUBMITTED' then
      raise exception 'Invalid status transition';
    end if;
    v_to := 'DRAFT';

    update public.case_assignments
       set status = v_to,
           submitted_at_ts = null,
           submitted_at_text = null,
           updated_at_ts = v_now,
           updated_at_text = v_now::timestamptz::text
     where id = p_assignment_id;
  elsif p_action = 'HR_REOPEN' then
    if v_from <> 'EMPLOYEE_SUBMITTED' then
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
     where id = p_assignment_id;
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
    p_assignment_id,
    v_actor,
    p_action,
    v_from,
    v_to,
    jsonb_build_object('note', v_note, 'at', v_now)
  );

  return jsonb_build_object(
    'success', true,
    'assignment_id', p_assignment_id,
    'from_status', v_from,
    'to_status', v_to
  );
end;
$$;

grant execute on function public.transition_assignment(text, text, text) to authenticated;
