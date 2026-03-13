-- Add created_by_user_id to quotes for vendor-submitted quote tracking
-- Uses text to match backend user id format (compatible with both SQLite and Supabase)
begin;
alter table public.quotes add column if not exists created_by_user_id text null;
create index if not exists idx_quotes_created_by on public.quotes(created_by_user_id);
commit;
