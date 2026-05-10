-- HR Feedback on Employee case - append-only log
-- assignment_id uses text to match case_assignments(id)

create table if not exists public.hr_feedback (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null references public.case_assignments(id) on delete cascade,
  hr_user_id uuid not null,
  employee_user_id uuid,
  message text not null,
  created_at timestamptz not null default now()
);

create index if not exists hr_feedback_assignment_id_created_idx
  on public.hr_feedback (assignment_id, created_at desc);

comment on table public.hr_feedback is 'Append-only log of HR feedback to employees';

-- VIEW: latest feedback per assignment (for "latest feedback" view)
create or replace view public.hr_feedback_latest as
select distinct on (assignment_id)
  id,
  assignment_id,
  hr_user_id,
  employee_user_id,
  message,
  created_at
from public.hr_feedback
order by assignment_id, created_at desc;

comment on view public.hr_feedback_latest is 'Latest feedback row per assignment_id';

-- RLS
alter table public.hr_feedback enable row level security;

-- HR: select only for assignments where hr_user_id = auth.uid()
create policy "hr_feedback_hr_select"
  on public.hr_feedback for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.id = hr_feedback.assignment_id
        and (ca.hr_user_id::uuid = auth.uid() or ca.hr_user_id = auth.uid()::text)
    )
  );

-- No INSERT policy for authenticated: inserts only via post_hr_feedback RPC (SECURITY DEFINER bypasses RLS)

-- Employee: select only for assignments where employee_user_id = auth.uid()
create policy "hr_feedback_employee_select"
  on public.hr_feedback for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.id = hr_feedback.assignment_id
        and (ca.employee_user_id::uuid = auth.uid() or ca.employee_user_id = auth.uid()::text)
    )
  );

-- No UPDATE/DELETE (append-only)
-- RLS defaults to deny for update/delete when no policy exists

grant select on public.hr_feedback to authenticated;
grant select on public.hr_feedback_latest to authenticated;

-- SECURITY DEFINER RPC: post feedback (HR only)
-- Resolves hr_user_id and employee_user_id from case_assignments; client cannot spoof
create or replace function public.post_hr_feedback(
  p_assignment_id text,
  p_message text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor uuid;
  v_hr_id text;
  v_emp_id uuid;
  v_row record;
begin
  v_actor := auth.uid();
  if v_actor is null then
    return jsonb_build_object('ok', false, 'error', 'Not authenticated');
  end if;

  -- Lock and fetch assignment
  select hr_user_id, employee_user_id
    into v_hr_id, v_emp_id
    from public.case_assignments
   where id = p_assignment_id
   for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'Assignment not found');
  end if;

  -- Must be the assigned HR
  if v_hr_id is null or (v_hr_id::uuid <> v_actor and v_hr_id <> v_actor::text) then
    return jsonb_build_object('ok', false, 'error', 'Not authorized to post feedback for this assignment');
  end if;

  if nullif(trim(p_message), '') is null then
    return jsonb_build_object('ok', false, 'error', 'Message cannot be empty');
  end if;

  insert into public.hr_feedback (assignment_id, hr_user_id, employee_user_id, message)
  values (p_assignment_id, v_actor, v_emp_id, trim(p_message))
  returning id, assignment_id, hr_user_id, employee_user_id, message, created_at
  into v_row;

  return jsonb_build_object(
    'ok', true,
    'id', v_row.id,
    'assignment_id', v_row.assignment_id,
    'message', v_row.message,
    'created_at', v_row.created_at
  );
end;
$$;

grant execute on function public.post_hr_feedback(text, text) to authenticated;

comment on function public.post_hr_feedback is 'HR posts feedback for an assignment. Resolves hr_user_id/employee_user_id server-side.';
