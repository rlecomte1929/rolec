-- AIQ-756 backfill — public.rfq_requests
-- Orphaned out-of-band table: created directly on prod, no in-repo CREATE, yet
-- ALTERed by the merged migration 20260606000000_rfq_immigration_context.sql
-- (which itself notes "the rfq_requests table ... is not owned by an in-repo
-- migration"). So a fresh replay aborts at that ALTER with 42P01. Placed one
-- step before 20260606000000 so the ADD COLUMN finds the table.
--
-- DDL is prod-as-oracle (2026-06-04), MINUS the immigration_context column —
-- that column is added by 20260606000000 (ADD COLUMN IF NOT EXISTS), so the
-- end state still matches prod. Idempotent; no-op on prod.
--
-- REPLAY-SAFE FK GUARD: like immigration_cases, the case_id -> relocation_cases
-- FK is added only when relocation_cases.id is uuid (it is on prod; still text
-- on a fresh baseline replay). Separate relocation_cases id->uuid fix tracked.

begin;

create table if not exists public.rfq_requests (
  id                   uuid        not null default gen_random_uuid(),
  case_id              uuid,
  vendor_id            uuid,
  org_id               text,
  service_category     text        not null,
  move_date            date,
  budget_range         text,
  special_requirements text,
  hr_user_id           text,
  hr_email             text,
  hr_name              text,
  status               text        not null default 'sent'::text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  quote_amount         numeric,
  quote_currency       text        default 'EUR'::text,
  quote_deadline       date,
  quote_deliverable    text,
  constraint rfq_requests_pkey primary key (id),
  constraint rfq_requests_status_check
    check (status = any (array['sent'::text, 'quote_received'::text, 'accepted'::text, 'cancelled'::text]))
);

-- Replay-safe FK: only when relocation_cases.id is uuid (baseline divergence).
do $$
begin
  if not exists (
        select 1 from pg_constraint
        where conname = 'rfq_requests_case_id_fkey'
          and conrelid = 'public.rfq_requests'::regclass)
     and (select data_type from information_schema.columns
          where table_schema = 'public' and table_name = 'relocation_cases'
            and column_name = 'id') = 'uuid'
  then
    alter table public.rfq_requests
      add constraint rfq_requests_case_id_fkey
      foreign key (case_id) references public.relocation_cases (id) on delete cascade;
  end if;
end $$;

create index if not exists rfq_requests_case_id_idx on public.rfq_requests (case_id);

alter table public.rfq_requests enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='rfq_requests' and policyname='rfq_requests_hr_read') then
    create policy rfq_requests_hr_read on public.rfq_requests
      for select to public using (org_id = current_setting('app.company_id'::text, true));
  end if;
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='rfq_requests' and policyname='rfq_requests_hr_insert') then
    create policy rfq_requests_hr_insert on public.rfq_requests
      for insert to public with check (org_id = current_setting('app.company_id'::text, true));
  end if;
  if not exists (select 1 from pg_policies where schemaname='public'
      and tablename='rfq_requests' and policyname='rfq_requests_hr_update') then
    create policy rfq_requests_hr_update on public.rfq_requests
      for update to public using (org_id = current_setting('app.company_id'::text, true));
  end if;
end $$;

revoke all on public.rfq_requests from anon;

commit;
