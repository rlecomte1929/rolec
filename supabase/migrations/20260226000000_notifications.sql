-- Option 6A: Notifications (in-app + DB)
-- Minimal notification system for HR <-> Employee collaboration
-- Prepares for 6B (realtime) and 6C (external delivery + preferences)

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  user_id uuid not null,
  assignment_id text,
  case_id text,
  type text not null,
  title text not null,
  body text,
  metadata jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  -- 6C prep: optional fields for future external delivery
  delivery_channel text,
  priority int
);

create index if not exists notifications_user_created_idx
  on public.notifications (user_id, created_at desc);
create index if not exists notifications_user_read_idx
  on public.notifications (user_id, read_at);
create index if not exists notifications_assignment_idx
  on public.notifications (assignment_id) where assignment_id is not null;

comment on table public.notifications is 'In-app notifications. Append-only with read_at updates. 6C: delivery_channel, priority for future use.';

-- Future 6C table (defined in comment for reference):
-- notification_preferences(user_id uuid, type text, in_app bool, email bool, push bool, mute_until timestamptz, ...)

alter table public.notifications enable row level security;

create policy "notifications_select_own"
  on public.notifications for select to authenticated
  using (user_id = auth.uid());

create policy "notifications_update_own_read"
  on public.notifications for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- No INSERT policy: inserts only via create_notification RPC (SECURITY DEFINER)

grant select, update on public.notifications to authenticated;

-- RPC: create_notification (SECURITY DEFINER)
-- Caller must be employee or HR for the assignment; creates notification for specified user_id
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
    if (v_row.employee_user_id::uuid <> v_actor and v_row.employee_user_id <> v_actor::text)
       and (v_row.hr_user_id::uuid <> v_actor and v_row.hr_user_id <> v_actor::text) then
      raise exception 'Not authorized to create notification for this assignment';
    end if;
  end if;

  insert into public.notifications (user_id, assignment_id, case_id, type, title, body, metadata)
  values (p_user_id, p_assignment_id, p_case_id, p_type, p_title, p_body, p_metadata)
  returning id into v_new_id;
  return v_new_id;
end;
$$;

grant execute on function public.create_notification(uuid, text, text, text, text, text, jsonb) to authenticated;

-- RPC: list_notifications (SECURITY INVOKER - respects RLS)
create or replace function public.list_notifications(
  p_limit int default 25,
  p_only_unread boolean default false
)
returns table (
  id uuid,
  created_at timestamptz,
  assignment_id text,
  case_id text,
  type text,
  title text,
  body text,
  metadata jsonb,
  read_at timestamptz
)
language sql
security invoker
set search_path = public
stable
as $$
  select n.id, n.created_at, n.assignment_id, n.case_id, n.type, n.title, n.body, n.metadata, n.read_at
  from public.notifications n
  where n.user_id = auth.uid()
    and (not p_only_unread or n.read_at is null)
  order by n.created_at desc
  limit least(p_limit, 100);
$$;

grant execute on function public.list_notifications(int, boolean) to authenticated;

-- RPC: mark_notification_read (SECURITY INVOKER)
create or replace function public.mark_notification_read(p_notification_id uuid)
returns boolean
language plpgsql
security invoker
set search_path = public
as $$
begin
  update public.notifications
  set read_at = now()
  where id = p_notification_id and user_id = auth.uid();
  return found;
end;
$$;

grant execute on function public.mark_notification_read(uuid) to authenticated;
