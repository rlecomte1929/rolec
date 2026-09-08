-- Option 6C: Update create_notification to apply preferences + muted_until + outbox

create or replace function public.create_notification(
  p_user_id uuid,
  p_type text,
  p_title text,
  p_body text default null,
  p_assignment_id text default null,
  p_case_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor uuid;
  v_row record;
  v_new_id uuid;
  v_pref record;
  v_in_app boolean := true;
  v_email boolean := false;
  v_muted_until timestamptz;
  v_to_email text;
begin
  v_actor := auth.uid();
  if v_actor is null then
    raise exception 'Not authenticated';
  end if;

  if p_assignment_id is not null then
    select employee_user_id, hr_user_id into v_row
    from public.case_assignments
    where id = p_assignment_id;
    if not found then
      raise exception 'Assignment not found';
    end if;
    if (v_row.employee_user_id::uuid <> v_actor and (v_row.employee_user_id::text) <> v_actor::text)
       and (v_row.hr_user_id::uuid <> v_actor and (v_row.hr_user_id::text) <> v_actor::text) then
      raise exception 'Not authorized to create notification for this assignment';
    end if;
  end if;

  -- Check preferences (default: in_app=true, email=false)
  select in_app, email, muted_until into v_pref
  from public.notification_preferences
  where user_id = p_user_id and type = p_type;
  if found then
    v_in_app := coalesce(v_pref.in_app, true);
    v_email := coalesce(v_pref.email, false);
    v_muted_until := v_pref.muted_until;
  end if;

  if v_muted_until is not null and v_muted_until > now() then
    return null;
  end if;

  if not v_in_app and not v_email then
    return null;
  end if;

  if v_in_app then
    insert into public.notifications (user_id, assignment_id, case_id, type, title, body, metadata, source, email_status)
    values (p_user_id, p_assignment_id, p_case_id, p_type, p_title, p_body, p_metadata, 'rpc',
      case when v_email then 'pending' else null end)
    returning id into v_new_id;
  elsif v_email then
    insert into public.notifications (user_id, assignment_id, case_id, type, title, body, metadata, source, email_status)
    values (p_user_id, p_assignment_id, p_case_id, p_type, p_title, p_body, p_metadata, 'rpc', 'pending')
    returning id into v_new_id;
  end if;

  if v_email then
    select email into v_to_email from auth.users where id = p_user_id;
    if v_to_email is not null and v_to_email != '' then
      insert into public.notification_outbox (notification_id, user_id, to_email, type, payload)
      values (v_new_id, p_user_id, v_to_email, p_type, jsonb_build_object(
        'title', p_title, 'body', p_body, 'assignment_id', p_assignment_id, 'case_id', p_case_id
      ) || coalesce(p_metadata, '{}'::jsonb));
    end if;
  end if;

  return v_new_id;
end;
$$;

grant execute on function public.create_notification(uuid, text, text, text, text, text, jsonb) to authenticated;
