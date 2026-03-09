-- Add optional external_key for import idempotency
-- Allows deterministic upsert when re-importing from structured sources
begin;

alter table public.country_resources add column if not exists external_key text;
create unique index if not exists idx_country_resources_external_key
  on public.country_resources(external_key) where external_key is not null;

alter table public.rkg_country_events add column if not exists external_key text;
create unique index if not exists idx_rkg_events_external_key
  on public.rkg_country_events(external_key) where external_key is not null;

commit;
