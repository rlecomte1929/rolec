-- Country-specific resource content for ReloPass Resources page
-- Run in Supabase SQL Editor: paste and execute
begin;

create table if not exists public.country_resource_sections (
  id uuid primary key default gen_random_uuid(),
  country_code text not null,
  city text null,
  section_key text not null,
  title text not null,
  content_json jsonb not null default '{}',
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_country_resource_sections_unique
  on public.country_resource_sections (country_code, coalesce(city, ''), section_key);

create index if not exists idx_country_resource_sections_lookup
  on public.country_resource_sections (country_code, city);

create table if not exists public.country_events (
  id uuid primary key default gen_random_uuid(),
  country_code text not null,
  city text null,
  name text not null,
  category text not null,
  description text,
  location text,
  start_date date,
  end_date date,
  price_min numeric null,
  price_max numeric null,
  booking_url text,
  source text,
  metadata_json jsonb default '{}',
  created_at timestamptz not null default now()
);

create index if not exists idx_country_events_lookup
  on public.country_events (country_code, city, category);

create table if not exists public.country_resource_items (
  id uuid primary key default gen_random_uuid(),
  section_id uuid not null references public.country_resource_sections(id) on delete cascade,
  item_type text not null,
  title text not null,
  description text,
  url text,
  metadata_json jsonb default '{}',
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_country_resource_items_section
  on public.country_resource_items (section_id);

commit;
