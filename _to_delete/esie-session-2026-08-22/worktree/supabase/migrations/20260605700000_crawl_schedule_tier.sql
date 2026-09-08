-- Per-tier crawl scheduling (AIQ-689 / P2-02a)
-- Adds a tier dimension to existing crawl_schedules so scheduled runs are
-- attributable to a freshness tier (tier-1-critical=daily, tier-1-stable=weekly,
-- tier-2=monthly). No new table; crawl_schedules already has RLS enabled.
begin;

alter table public.crawl_schedules
  add column if not exists crawl_tier text; -- tier-1-critical, tier-1-stable, tier-2

create index if not exists idx_crawl_schedules_tier on public.crawl_schedules(crawl_tier);

commit;
