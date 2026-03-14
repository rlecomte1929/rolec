-- Relocation Knowledge Graph (RKG) - Structured resources for country-specific content
-- Supports future expansion: crawlers, APIs, reviewer workflows, immigration/compliance
begin;

-- 5.1 resource_categories: canonical sections on the Resources page
create table if not exists public.resource_categories (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  label text not null,
  description text,
  icon_name text,
  sort_order int not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 5.2 resource_sources: provenance and trust
create table if not exists public.resource_sources (
  id uuid primary key default gen_random_uuid(),
  source_name text not null unique,
  publisher text,
  source_type text not null, -- official, institutional, commercial, community, internal_curated
  url text,
  retrieved_at timestamptz,
  content_hash text,
  notes text,
  trust_tier text not null default 'T2', -- T0=official, T1=institutional, T2=commercial, T3=community
  created_at timestamptz not null default now()
);

-- 5.3 resource_tags: reusable filters and navigation tags
create table if not exists public.resource_tags (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  label text not null,
  tag_group text, -- family_type, budget, interest, age_group, indoor_outdoor, free_paid, weekday_weekend
  created_at timestamptz not null default now()
);

-- 5.4 country_resources: content entries per country/city/category
create table if not exists public.country_resources (
  id uuid primary key default gen_random_uuid(),
  country_code text not null,
  country_name text,
  city_name text,
  category_id uuid references public.resource_categories(id) on delete restrict,
  title text not null,
  summary text,
  body text,
  content_json jsonb default '{}',
  resource_type text not null default 'guide', -- guide, checklist_item, provider, place, event_source, tip, official_link
  audience_type text not null default 'all', -- all, single, couple, family, with_children, spouse_job_seeker
  min_child_age int,
  max_child_age int,
  budget_tier text, -- low, mid, high
  language_code text,
  is_family_friendly boolean not null default false,
  is_featured boolean not null default false,
  address text,
  district text,
  latitude numeric,
  longitude numeric,
  price_range_text text,
  external_url text,
  booking_url text,
  contact_info text,
  opening_hours text,
  source_id uuid references public.resource_sources(id) on delete set null,
  trust_tier text,
  effective_from date,
  effective_to date,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_country_resources_country on public.country_resources(country_code);
create index if not exists idx_country_resources_city on public.country_resources(city_name);
create index if not exists idx_country_resources_category on public.country_resources(category_id);
create index if not exists idx_country_resources_audience on public.country_resources(audience_type);
create index if not exists idx_country_resources_active on public.country_resources(is_active);
create index if not exists idx_country_resources_family on public.country_resources(is_family_friendly);
create index if not exists idx_country_resources_country_city on public.country_resources(country_code, city_name);

-- 5.5 country_resource_tags: many-to-many
create table if not exists public.country_resource_tags (
  id uuid primary key default gen_random_uuid(),
  resource_id uuid not null references public.country_resources(id) on delete cascade,
  tag_id uuid not null references public.resource_tags(id) on delete cascade,
  unique(resource_id, tag_id)
);

create index if not exists idx_country_resource_tags_resource on public.country_resource_tags(resource_id);
create index if not exists idx_country_resource_tags_tag on public.country_resource_tags(tag_id);

-- 5.6 country_events: structured events, cinema, concerts, festivals (replaces simpler country_events if exists)
-- Use a new table to avoid conflicts with existing country_events
create table if not exists public.rkg_country_events (
  id uuid primary key default gen_random_uuid(),
  country_code text not null,
  city_name text not null,
  title text not null,
  description text,
  event_type text not null, -- cinema, concert, festival, sports, family_activity, networking, museum, theater
  venue_name text,
  address text,
  start_datetime timestamptz not null,
  end_datetime timestamptz,
  price_text text,
  currency text,
  is_free boolean not null default false,
  is_family_friendly boolean not null default false,
  min_age int,
  max_age int,
  language_code text,
  external_url text,
  booking_url text,
  source_id uuid references public.resource_sources(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_rkg_events_country on public.rkg_country_events(country_code);
create index if not exists idx_rkg_events_city on public.rkg_country_events(city_name);
create index if not exists idx_rkg_events_type on public.rkg_country_events(event_type);
create index if not exists idx_rkg_events_start on public.rkg_country_events(start_datetime);
create index if not exists idx_rkg_events_family on public.rkg_country_events(is_family_friendly);

-- 5.7 case_resource_preferences: user filter preferences
create table if not exists public.case_resource_preferences (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null,
  preferred_budget_tier text,
  preferred_interests jsonb,
  preferred_languages jsonb,
  weekend_only boolean not null default false,
  family_mode boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_case_resource_prefs_case on public.case_resource_preferences(case_id);

-- RLS (read for authenticated, write for admin later)
alter table public.resource_categories enable row level security;
alter table public.resource_sources enable row level security;
alter table public.resource_tags enable row level security;
alter table public.country_resources enable row level security;
alter table public.country_resource_tags enable row level security;
alter table public.rkg_country_events enable row level security;
alter table public.case_resource_preferences enable row level security;

drop policy if exists "resource_categories_read" on public.resource_categories;
create policy "resource_categories_read" on public.resource_categories for select using (true);
drop policy if exists "resource_sources_read" on public.resource_sources;
create policy "resource_sources_read" on public.resource_sources for select using (true);
drop policy if exists "resource_tags_read" on public.resource_tags;
create policy "resource_tags_read" on public.resource_tags for select using (true);
drop policy if exists "country_resources_read" on public.country_resources;
create policy "country_resources_read" on public.country_resources for select using (true);
drop policy if exists "country_resource_tags_read" on public.country_resource_tags;
create policy "country_resource_tags_read" on public.country_resource_tags for select using (true);
drop policy if exists "rkg_country_events_read" on public.rkg_country_events;
create policy "rkg_country_events_read" on public.rkg_country_events for select using (true);
drop policy if exists "case_resource_preferences_all" on public.case_resource_preferences;
create policy "case_resource_preferences_all" on public.case_resource_preferences for all using (true);

commit;
