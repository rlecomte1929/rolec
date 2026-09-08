-- Collaboration notifications: user-targeted alerts for mentions, replies, thread reopen
-- Admin-only; integrates with collaboration threads
begin;

create table if not exists public.collaboration_notifications (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  notification_type text not null,
  thread_id uuid not null references public.collaboration_threads(id) on delete cascade,
  comment_id uuid references public.collaboration_comments(id) on delete set null,
  actor_user_id text,
  created_at timestamptz not null default now(),
  read_at timestamptz
);

create index if not exists idx_collab_notif_user on public.collaboration_notifications(user_id);
create index if not exists idx_collab_notif_user_unread on public.collaboration_notifications(user_id, read_at) where read_at is null;
create index if not exists idx_collab_notif_created on public.collaboration_notifications(created_at desc);

alter table public.collaboration_notifications enable row level security;
create policy "collab_notif_admin" on public.collaboration_notifications for all using (true) with check (true);

commit;
