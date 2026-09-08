-- Collaboration threads: internal admin discussion on queue items, notifications, staged candidates, live resources/events
-- Admin-only; one thread per object; comments with replies and mentions
begin;

create table if not exists public.collaboration_threads (
  id uuid primary key default gen_random_uuid(),
  thread_target_type text not null,
  thread_target_id text not null,
  title text,
  status text not null default 'open',
  created_by_user_id text not null,
  resolved_by_user_id text,
  resolved_at timestamptz,
  last_comment_at timestamptz,
  last_comment_by_user_id text,
  comment_count int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_collab_threads_target
  on public.collaboration_threads(thread_target_type, thread_target_id);

create index if not exists idx_collab_threads_status on public.collaboration_threads(status);
create index if not exists idx_collab_threads_last_comment on public.collaboration_threads(last_comment_at desc nulls last);

create table if not exists public.collaboration_comments (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.collaboration_threads(id) on delete cascade,
  parent_comment_id uuid references public.collaboration_comments(id) on delete cascade,
  author_user_id text not null,
  body text not null,
  body_format text not null default 'plain_text',
  is_edited boolean not null default false,
  edited_at timestamptz,
  deleted_at timestamptz,
  deleted_by_user_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_collab_comments_thread on public.collaboration_comments(thread_id);
create index if not exists idx_collab_comments_parent on public.collaboration_comments(parent_comment_id);
create index if not exists idx_collab_comments_created on public.collaboration_comments(created_at);

create table if not exists public.collaboration_comment_mentions (
  id uuid primary key default gen_random_uuid(),
  comment_id uuid not null references public.collaboration_comments(id) on delete cascade,
  mentioned_user_id text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_collab_mentions_comment on public.collaboration_comment_mentions(comment_id);
create index if not exists idx_collab_mentions_user on public.collaboration_comment_mentions(mentioned_user_id);

create table if not exists public.collaboration_thread_participants (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.collaboration_threads(id) on delete cascade,
  user_id text not null,
  role_in_thread text,
  last_read_comment_id uuid references public.collaboration_comments(id) on delete set null,
  last_read_at timestamptz,
  is_subscribed boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(thread_id, user_id)
);

create index if not exists idx_collab_participants_thread on public.collaboration_thread_participants(thread_id);
create index if not exists idx_collab_participants_user on public.collaboration_thread_participants(user_id);

alter table public.collaboration_threads enable row level security;
alter table public.collaboration_comments enable row level security;
alter table public.collaboration_comment_mentions enable row level security;
alter table public.collaboration_thread_participants enable row level security;
create policy "collab_threads_admin" on public.collaboration_threads for all using (true) with check (true);
create policy "collab_comments_admin" on public.collaboration_comments for all using (true) with check (true);
create policy "collab_mentions_admin" on public.collaboration_comment_mentions for all using (true) with check (true);
create policy "collab_participants_admin" on public.collaboration_thread_participants for all using (true) with check (true);

commit;
