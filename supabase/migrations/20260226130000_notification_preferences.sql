-- Option 6C: Notification preferences per user and type

create table if not exists public.notification_preferences (
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null,
  in_app boolean not null default true,
  email boolean not null default false,
  muted_until timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, type)
);

create index if not exists idx_notification_preferences_user
  on public.notification_preferences (user_id);

alter table public.notification_preferences enable row level security;

create policy "notification_preferences_select_own"
  on public.notification_preferences for select to authenticated
  using (user_id = auth.uid());

create policy "notification_preferences_insert_own"
  on public.notification_preferences for insert to authenticated
  with check (user_id = auth.uid());

create policy "notification_preferences_update_own"
  on public.notification_preferences for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

grant select, insert, update on public.notification_preferences to authenticated;

comment on table public.notification_preferences is 'Per-user, per-type notification delivery preferences (6C).';

-- RPC: upsert_notification_preference (SECURITY INVOKER)
create or replace function public.upsert_notification_preference(
  p_type text,
  p_in_app boolean default true,
  p_email boolean default false,
  p_muted_until timestamptz default null
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_uid uuid;
begin
  v_uid := auth.uid();
  if v_uid is null then
    raise exception 'Not authenticated';
  end if;

  insert into public.notification_preferences (user_id, type, in_app, email, muted_until, updated_at)
  values (v_uid, p_type, p_in_app, p_email, p_muted_until, now())
  on conflict (user_id, type) do update set
    in_app = excluded.in_app,
    email = excluded.email,
    muted_until = excluded.muted_until,
    updated_at = now();
end;
$$;

grant execute on function public.upsert_notification_preference(text, boolean, boolean, timestamptz) to authenticated;
