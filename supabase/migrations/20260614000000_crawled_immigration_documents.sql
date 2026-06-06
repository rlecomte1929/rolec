-- crawled_immigration_documents: stores raw crawled pages for immigration content
-- Applied to prod via AIQ-756 discipline; adding repo file to reconcile ledger

begin;

create table if not exists public.crawled_immigration_documents (
    id             uuid        not null default gen_random_uuid() primary key,
    corridor       varchar     not null,
    source_url     text        not null,
    trust_tier     integer     not null default 2,
    raw_html_path  text,
    extracted_text text,
    content_hash   text        not null,
    fetched_at     timestamptz not null default now(),
    http_status    integer,
    crawl_error    text,
    is_active      boolean     default true
  );

alter table public.crawled_immigration_documents enable row level security;

do $$
begin
  if not exists (
      select 1 from pg_policies
      where tablename = 'crawled_immigration_documents'
        and policyname = 'cid_select_authenticated'
    ) then
    execute $p$
      create policy cid_select_authenticated
        on public.crawled_immigration_documents
        for select
        to authenticated
        using (true)
    $p$;
  end if;
end $$;

commit;
