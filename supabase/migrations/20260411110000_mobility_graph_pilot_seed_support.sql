-- Columns needed for MVP pilot seed: scenario fields, JSON rule conditions, document keys, demo metadata

begin;

alter table public.mobility_cases
  add column if not exists origin_country text,
  add column if not exists destination_country text,
  add column if not exists case_type text,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.requirements_catalog
  add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.policy_rules
  add column if not exists conditions jsonb not null default '{}'::jsonb,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.case_documents
  add column if not exists document_key text;

commit;
