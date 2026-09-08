-- Add priority and assignee to support_cases for ticket-style workflow
-- priority: low | medium | high | urgent
-- status (existing): open | investigating | blocked | resolved
-- category (existing): bug | feature request | onboarding | policy question | supplier issue | other
begin;

alter table public.support_cases
  add column if not exists priority text default 'medium'
    check (priority in ('low', 'medium', 'high', 'urgent'));
alter table public.support_cases
  add column if not exists assignee_id text null;

create index if not exists idx_support_cases_priority on public.support_cases(priority);
create index if not exists idx_support_cases_assignee on public.support_cases(assignee_id);

comment on column public.support_cases.priority is 'Ticket priority: low, medium, high, urgent';
comment on column public.support_cases.assignee_id is 'Profile ID of assigned admin/HR';

commit;
