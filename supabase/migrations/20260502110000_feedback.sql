-- In-app feedback widget — one row per submission from a logged-in pilot user.
-- Distinct from public.case_feedback (HR review of relocation cases).

create table if not exists public.feedback (
  id          uuid        primary key default gen_random_uuid(),
  user_id     uuid        references auth.users(id) on delete set null,
  page_url    text        not null,
  category    text        not null default 'other'
                          check (category in ('bug', 'idea', 'other')),
  message     text        not null check (char_length(message) between 1 and 2000),
  status      text        not null default 'new'
                          check (status in ('new', 'reviewed', 'acted_on')),
  created_at  timestamptz not null default now()
);

create index if not exists feedback_status_idx     on public.feedback(status);
create index if not exists feedback_created_at_idx on public.feedback(created_at desc);

-- RLS
alter table public.feedback enable row level security;

-- Authenticated users can insert their own feedback.
create policy "authenticated users can submit feedback"
  on public.feedback for insert
  to authenticated
  with check (auth.uid() = user_id);

-- Admin SELECT/UPDATE — same pattern as Phase 1 (profiles.id is text, role is 'ADMIN').
create policy "admin can read feedback"
  on public.feedback for select
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid()::text
        and role = 'ADMIN'
    )
  );

create policy "admin can update feedback"
  on public.feedback for update
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid()::text
        and role = 'ADMIN'
    )
  );
