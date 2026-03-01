begin;

create table if not exists public.vendors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  service_types text[] not null default '{}',
  countries text[] not null default '{}',
  logo_url text null,
  contact_email text null,
  status text not null default 'active' check (status in ('active','pending')),
  created_at timestamptz not null default now()
);

create table if not exists public.vendor_users (
  user_id uuid primary key references auth.users(id),
  vendor_id uuid not null references public.vendors(id),
  role text not null default 'vendor_agent' check (role in ('vendor_admin','vendor_agent')),
  created_at timestamptz not null default now()
);

create table if not exists public.case_service_answers (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  service_key text not null,
  answers jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_case_service_answers_unique
  on public.case_service_answers (case_id, service_key);

create index if not exists idx_case_service_answers_case
  on public.case_service_answers (case_id);

create table if not exists public.service_recommendations (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  service_key text not null,
  vendor_id uuid not null references public.vendors(id),
  match_score numeric null,
  estimated_min numeric null,
  estimated_max numeric null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_service_recommendations_case
  on public.service_recommendations (case_id);

create table if not exists public.case_vendor_shortlist (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  service_key text not null,
  vendor_id uuid not null references public.vendors(id),
  selected boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_case_vendor_shortlist_case
  on public.case_vendor_shortlist (case_id);

create table if not exists public.rfqs (
  id uuid primary key default gen_random_uuid(),
  rfq_ref text unique not null,
  case_id text not null,
  created_by_user_id uuid not null references auth.users(id),
  status text not null default 'draft' check (status in ('draft','sent','closed')),
  created_at timestamptz not null default now()
);

create table if not exists public.rfq_items (
  id uuid primary key default gen_random_uuid(),
  rfq_id uuid not null references public.rfqs(id) on delete cascade,
  service_key text not null,
  requirements jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.rfq_recipients (
  id uuid primary key default gen_random_uuid(),
  rfq_id uuid not null references public.rfqs(id) on delete cascade,
  vendor_id uuid not null references public.vendors(id),
  status text not null default 'sent' check (status in ('sent','viewed','replied','declined')),
  last_activity_at timestamptz null
);

create table if not exists public.quote_conversations (
  id uuid primary key default gen_random_uuid(),
  thread_type text not null default 'vendor_quote' check (thread_type in ('hr_case','vendor_quote')),
  case_id text null,
  rfq_id uuid null references public.rfqs(id),
  created_at timestamptz not null default now()
);

create table if not exists public.quote_participants (
  conversation_id uuid not null references public.quote_conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id),
  role text not null check (role in ('employee','hr','vendor')),
  created_at timestamptz not null default now(),
  primary key (conversation_id, user_id)
);

create table if not exists public.quote_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.quote_conversations(id) on delete cascade,
  sender_user_id uuid not null references auth.users(id),
  body text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.quotes (
  id uuid primary key default gen_random_uuid(),
  rfq_id uuid not null references public.rfqs(id) on delete cascade,
  vendor_id uuid not null references public.vendors(id),
  currency text not null default 'EUR',
  total_amount numeric not null,
  valid_until date null,
  status text not null default 'proposed' check (status in ('proposed','accepted','rejected')),
  created_at timestamptz not null default now()
);

create table if not exists public.quote_lines (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null references public.quotes(id) on delete cascade,
  label text not null,
  amount numeric not null
);

alter table public.vendors enable row level security;
alter table public.vendor_users enable row level security;
alter table public.case_service_answers enable row level security;
alter table public.service_recommendations enable row level security;
alter table public.case_vendor_shortlist enable row level security;
alter table public.rfqs enable row level security;
alter table public.rfq_items enable row level security;
alter table public.rfq_recipients enable row level security;
alter table public.quote_conversations enable row level security;
alter table public.quote_participants enable row level security;
alter table public.quote_messages enable row level security;
alter table public.quotes enable row level security;
alter table public.quote_lines enable row level security;

-- Vendors: read for authenticated users, write for service_role
drop policy if exists vendors_select on public.vendors;
create policy vendors_select on public.vendors for select to authenticated using (true);
drop policy if exists vendors_write on public.vendors;
create policy vendors_write on public.vendors for all to service_role using (true) with check (true);

drop policy if exists vendor_users_select on public.vendor_users;
create policy vendor_users_select on public.vendor_users for select to authenticated
  using (user_id = auth.uid());

-- Case-bound tables: employee or HR on assignment
drop policy if exists case_service_answers_access on public.case_service_answers;
create policy case_service_answers_access on public.case_service_answers
  for all to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_service_answers.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_service_answers.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists service_recommendations_access on public.service_recommendations;
create policy service_recommendations_access on public.service_recommendations
  for all to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = service_recommendations.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = service_recommendations.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists case_vendor_shortlist_access on public.case_vendor_shortlist;
create policy case_vendor_shortlist_access on public.case_vendor_shortlist
  for all to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_vendor_shortlist.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_vendor_shortlist.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists rfqs_access on public.rfqs;
create policy rfqs_access on public.rfqs
  for all to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = rfqs.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = rfqs.case_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists rfq_items_access on public.rfq_items;
create policy rfq_items_access on public.rfq_items
  for all to authenticated
  using (
    exists (
      select 1 from public.rfqs r
      join public.case_assignments ca on ca.case_id = r.case_id
      where r.id = rfq_items.rfq_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1 from public.rfqs r
      join public.case_assignments ca on ca.case_id = r.case_id
      where r.id = rfq_items.rfq_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists rfq_recipients_select on public.rfq_recipients;
create policy rfq_recipients_select on public.rfq_recipients
  for select to authenticated
  using (
    exists (
      select 1 from public.vendor_users vu
      where vu.vendor_id = rfq_recipients.vendor_id
        and vu.user_id = auth.uid()
    )
    or exists (
      select 1 from public.rfqs r
      join public.case_assignments ca on ca.case_id = r.case_id
      where r.id = rfq_recipients.rfq_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists quote_conversations_select on public.quote_conversations;
create policy quote_conversations_select on public.quote_conversations
  for select to authenticated
  using (
    exists (
      select 1 from public.quote_participants p
      where p.conversation_id = quote_conversations.id
        and p.user_id = auth.uid()
    )
  );

drop policy if exists quote_participants_access on public.quote_participants;
create policy quote_participants_access on public.quote_participants
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

drop policy if exists quote_messages_access on public.quote_messages;
create policy quote_messages_access on public.quote_messages
  for all to authenticated
  using (
    exists (
      select 1 from public.quote_participants p
      where p.conversation_id = quote_messages.conversation_id
        and p.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.quote_participants p
      where p.conversation_id = quote_messages.conversation_id
        and p.user_id = auth.uid()
    )
  );

drop policy if exists quotes_access on public.quotes;
create policy quotes_access on public.quotes
  for all to authenticated
  using (
    exists (
      select 1 from public.rfq_recipients rr
      join public.vendor_users vu on vu.vendor_id = rr.vendor_id
      where rr.rfq_id = quotes.rfq_id
        and vu.user_id = auth.uid()
    )
    or exists (
      select 1 from public.rfqs r
      join public.case_assignments ca on ca.case_id = r.case_id
      where r.id = quotes.rfq_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1 from public.rfqs r
      join public.case_assignments ca on ca.case_id = r.case_id
      where r.id = quotes.rfq_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists quote_lines_access on public.quote_lines;
create policy quote_lines_access on public.quote_lines
  for all to authenticated
  using (
    exists (
      select 1 from public.quotes q
      join public.rfqs r on r.id = q.rfq_id
      join public.case_assignments ca on ca.case_id = r.case_id
      where q.id = quote_lines.quote_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  )
  with check (
    exists (
      select 1 from public.quotes q
      join public.rfqs r on r.id = q.rfq_id
      join public.case_assignments ca on ca.case_id = r.case_id
      where q.id = quote_lines.quote_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

create or replace function public.create_rfq_with_items(
  p_case_id text,
  p_creator uuid,
  p_rfq_ref text,
  p_items jsonb,
  p_vendor_ids uuid[]
) returns uuid
language plpgsql
security definer
as $$
declare
  v_rfq_id uuid;
  v_convo_id uuid;
  v_item jsonb;
begin
  insert into public.rfqs (rfq_ref, case_id, created_by_user_id, status)
  values (p_rfq_ref, p_case_id, p_creator, 'sent')
  returning id into v_rfq_id;

  for v_item in select * from jsonb_array_elements(p_items) loop
    insert into public.rfq_items (rfq_id, service_key, requirements)
    values (
      v_rfq_id,
      coalesce(v_item->>'service_key', 'unknown'),
      coalesce(v_item->'requirements', '{}'::jsonb)
    );
  end loop;

  insert into public.rfq_recipients (rfq_id, vendor_id, status)
  select v_rfq_id, unnest(p_vendor_ids), 'sent';

  insert into public.quote_conversations (thread_type, case_id, rfq_id)
  values ('vendor_quote', p_case_id, v_rfq_id)
  returning id into v_convo_id;

  insert into public.quote_participants (conversation_id, user_id, role)
  values (v_convo_id, p_creator, 'employee');

  return v_rfq_id;
end;
$$;

grant execute on function public.create_rfq_with_items(text, uuid, text, jsonb, uuid[]) to authenticated;

commit;
