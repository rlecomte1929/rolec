-- Reopen/unsubmit assignment RPCs (public schema, additive).
-- Guarded so local supabase start doesn't fail before core tables exist.

do $do$
begin
  if exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'case_assignments')
     and exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'assignment_audit_log') then
    execute $fn$
create or replace function public.employee_unsubmit_assignment(p_assignment_id text)
returns jsonb
language plpgsql
as $$
declare
  assignment_row public.case_assignments%rowtype;
  from_status text;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  select *
    into assignment_row
    from public.case_assignments
   where id = p_assignment_id
   for update;

  if not found then
    raise exception 'Assignment not found';
  end if;

  if assignment_row.employee_user_id is null
     or assignment_row.employee_user_id <> auth.uid()::text then
    raise exception 'Not authorized';
  end if;

  from_status := assignment_row.status;

  if from_status <> 'EMPLOYEE_SUBMITTED' then
    raise exception 'Invalid status transition';
  end if;

  update public.case_assignments
     set status = 'DRAFT',
         submitted_at_text = null,
         updated_at_text = now()::timestamptz::text
   where id = p_assignment_id;

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
    auth.uid(),
    'EMPLOYEE_UNSUBMIT',
    from_status,
    'DRAFT',
    jsonb_build_object('at', now())
  );

  return jsonb_build_object(
    'assignment_id', p_assignment_id,
    'status', 'DRAFT'
  );
end;
$$;
    $fn$;

    execute $fn$
create or replace function public.hr_reopen_assignment(p_assignment_id text, p_hr_note text default null)
returns jsonb
language plpgsql
as $$
declare
  assignment_row public.case_assignments%rowtype;
  from_status text;
  note_text text;
  note_line text;
begin
  if auth.uid() is null then
    raise exception 'Not authenticated';
  end if;

  select *
    into assignment_row
    from public.case_assignments
   where id = p_assignment_id
   for update;

  if not found then
    raise exception 'Assignment not found';
  end if;

  if assignment_row.hr_user_id is null
     or assignment_row.hr_user_id <> auth.uid()::text then
    raise exception 'Not authorized';
  end if;

  from_status := assignment_row.status;

  if from_status not in ('EMPLOYEE_SUBMITTED', 'HR_REVIEW') then
    raise exception 'Invalid status transition';
  end if;

  note_text := nullif(trim(coalesce(p_hr_note, '')), '');
  if note_text is not null then
    note_line := to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') || ' ' || note_text;
  end if;

  update public.case_assignments
     set status = 'DRAFT',
         submitted_at_text = null,
         updated_at_text = now()::timestamptz::text,
         hr_notes = case
           when note_text is null then hr_notes
           when hr_notes is null or hr_notes = '' then note_line
           else hr_notes || E'\n' || note_line
         end
   where id = p_assignment_id;

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
    auth.uid(),
    'HR_REOPEN',
    from_status,
    'DRAFT',
    jsonb_build_object('at', now(), 'hr_note', note_text)
  );

  return jsonb_build_object(
    'assignment_id', p_assignment_id,
    'status', 'DRAFT'
  );
end;
$$;
    $fn$;

    execute 'grant execute on function public.employee_unsubmit_assignment(text) to authenticated';
    execute 'grant execute on function public.hr_reopen_assignment(text, text) to authenticated';
  else
    raise notice 'Skipping reopen/unsubmit RPCs; core tables not created yet.';
  end if;
end $do$;
