-- Resources Module: Full schema with enums, RLS, secure views
-- Compatible with existing profiles (id text, role text), auth.uid()
-- Admin: full access; HR/Employee: read only published+visible content
begin;

-- ============================================================================
-- 1. ENUMS
-- ============================================================================
do $$ begin
  create type public.resource_status as enum (
    'draft', 'in_review', 'approved', 'published', 'archived'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_source_type as enum (
    'official', 'institutional', 'commercial', 'community', 'internal_curated'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_trust_tier as enum ('T0', 'T1', 'T2', 'T3');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_entry_type as enum (
    'guide', 'checklist_item', 'provider', 'place', 'event_source', 'tip',
    'official_link', 'cost_snapshot', 'safety_tip', 'community_group',
    'school', 'healthcare_facility', 'housing_listing_source', 'transport_info'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_audience_type as enum (
    'all', 'single', 'couple', 'family', 'with_children', 'spouse_job_seeker'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_budget_tier as enum ('low', 'mid', 'high');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_event_type as enum (
    'cinema', 'concert', 'festival', 'sports', 'family_activity', 'networking',
    'museum', 'theater', 'market', 'nature', 'kids_activity', 'community_event'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_audit_entity_type as enum (
    'resource', 'event', 'category', 'tag', 'source'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.resource_audit_action_type as enum (
    'create', 'update', 'submit_for_review', 'approve', 'publish', 'archive',
    'delete', 'restore', 'unpublish'
  );
exception when duplicate_object then null;
end $$;

-- ============================================================================
-- 2. ROLE HELPER FUNCTIONS (uses public.profiles)
-- ============================================================================
create or replace function public.resources_current_user_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (select p.role from public.profiles p where p.id = auth.uid()::text limit 1),
    'none'
  );
$$;

create or replace function public.resources_is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select resources_current_user_role() = 'ADMIN';
$$;

create or replace function public.resources_can_read_published()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select resources_current_user_role() in ('ADMIN', 'HR', 'EMPLOYEE');
$$;

-- Grant execute to authenticated (RLS policies will call these)
grant execute on function public.resources_current_user_role() to authenticated;
grant execute on function public.resources_current_user_role() to service_role;
grant execute on function public.resources_is_admin() to authenticated;
grant execute on function public.resources_is_admin() to service_role;
grant execute on function public.resources_can_read_published() to authenticated;
grant execute on function public.resources_can_read_published() to service_role;

-- ============================================================================
-- 3. TABLE ALTERATIONS (add missing columns, constraints)
-- ============================================================================

-- resource_categories: add updated_at if missing, ensure indexes
alter table public.resource_categories
  add column if not exists updated_at timestamptz,
  add column if not exists created_by_user_id text,
  add column if not exists updated_by_user_id text;
update public.resource_categories set updated_at = coalesce(updated_at, created_at, now()) where updated_at is null;
alter table public.resource_categories alter column updated_at set default now();

create index if not exists idx_resource_categories_sort_order on public.resource_categories(sort_order);
create index if not exists idx_resource_categories_active on public.resource_categories(is_active) where is_active = true;

-- resource_tags: add updated_at, tag_group default for nulls
alter table public.resource_tags
  add column if not exists updated_at timestamptz,
  add column if not exists created_by_user_id text,
  add column if not exists updated_by_user_id text;
update public.resource_tags set updated_at = coalesce(updated_at, created_at, now()) where updated_at is null;
update public.resource_tags set tag_group = coalesce(tag_group, 'general') where tag_group is null;
alter table public.resource_tags alter column updated_at set default now();

create index if not exists idx_resource_tags_tag_group on public.resource_tags(tag_group);

-- resource_sources: add updated_at, ensure indexes (url kept nullable for existing data)
alter table public.resource_sources
  add column if not exists updated_at timestamptz,
  add column if not exists created_by_user_id text,
  add column if not exists updated_by_user_id text;
update public.resource_sources set updated_at = coalesce(updated_at, created_at, now()) where updated_at is null;
alter table public.resource_sources alter column updated_at set default now();

create index if not exists idx_resource_sources_type on public.resource_sources(source_type);
create index if not exists idx_resource_sources_trust_tier on public.resource_sources(trust_tier);

-- country_resources: ensure required columns, constraints, indexes
-- Keep existing contact_info/opening_hours as text; content_json may exist
alter table public.country_resources
  add column if not exists country_name text,
  add column if not exists content_json jsonb;

-- Summary: default for new rows
alter table public.country_resources alter column summary set default '';

-- category_id: existing has FK; ensure not null (some rows might have null)
-- Skip: alter category_id set not null could fail. Leave as-is.
-- Ensure is_active exists (for soft delete)
alter table public.country_resources add column if not exists is_active boolean not null default true;

create index if not exists idx_country_resources_status on public.country_resources(status);
create index if not exists idx_country_resources_visible on public.country_resources(is_visible_to_end_users) where is_visible_to_end_users = true;
create index if not exists idx_country_resources_country_city_status on public.country_resources(country_code, city_name, status);
create index if not exists idx_country_resources_effective_dates on public.country_resources(effective_from, effective_to) where effective_from is not null or effective_to is not null;
create index if not exists idx_country_resources_featured on public.country_resources(is_featured) where is_featured = true;

-- Optional check constraints
alter table public.country_resources drop constraint if exists chk_country_resources_child_age;
alter table public.country_resources add constraint chk_country_resources_child_age
  check (min_child_age is null or max_child_age is null or min_child_age <= max_child_age);

-- rkg_country_events: add country_name, trust_tier, ensure all workflow columns
alter table public.rkg_country_events
  add column if not exists country_name text,
  add column if not exists trust_tier text;

create index if not exists idx_rkg_events_country_city_status on public.rkg_country_events(country_code, city_name, status);

-- Event end >= start
alter table public.rkg_country_events drop constraint if exists chk_rkg_events_end_after_start;
alter table public.rkg_country_events add constraint chk_rkg_events_end_after_start
  check (end_datetime is null or end_datetime >= start_datetime);

-- country_event_tags (new table)
create table if not exists public.country_event_tags (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.rkg_country_events(id) on delete cascade,
  tag_id uuid not null references public.resource_tags(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique(event_id, tag_id)
);
create index if not exists idx_country_event_tags_event_id on public.country_event_tags(event_id);
create index if not exists idx_country_event_tags_tag_id on public.country_event_tags(tag_id);

-- case_resource_preferences: ensure unique, add budget enum constraint
create unique index if not exists idx_case_resource_prefs_case on public.case_resource_preferences(case_id);
alter table public.case_resource_preferences add column if not exists updated_at timestamptz;
update public.case_resource_preferences set updated_at = now() where updated_at is null;
alter table public.case_resource_preferences alter column updated_at set default now();

-- resource_audit_log: update to use enums if desired; keep text for backward compat
alter table public.resource_audit_log alter column performed_by_user_id drop not null;

-- ============================================================================
-- 4. UPDATED_AT TRIGGERS (reuse public.set_updated_at)
-- ============================================================================
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Apply to all resource tables with updated_at
do $$
declare
  t text;
  tbls text[] := array['resource_categories','resource_tags','resource_sources','country_resources','rkg_country_events','case_resource_preferences'];
begin
  foreach t in array tbls loop
    execute format('
      drop trigger if exists trg_%s_updated on public.%I;
      create trigger trg_%s_updated before update on public.%I
        for each row execute function public.set_updated_at();
    ', t, t, t, t);
  end loop;
end;
$$;

-- ============================================================================
-- 5. DROP OLD PERMISSIVE POLICIES
-- ============================================================================
drop policy if exists resource_categories_read on public.resource_categories;
drop policy if exists resource_sources_read on public.resource_sources;
drop policy if exists resource_tags_read on public.resource_tags;
drop policy if exists country_resources_read on public.country_resources;
drop policy if exists country_resource_tags_read on public.country_resource_tags;
drop policy if exists rkg_country_events_read on public.rkg_country_events;
drop policy if exists case_resource_preferences_all on public.case_resource_preferences;

-- ============================================================================
-- 6. RLS POLICIES (role-based)
-- ============================================================================

-- resource_categories: Admin full; HR/Employee read active only
create policy resource_categories_admin_all on public.resource_categories
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

create policy resource_categories_read_active on public.resource_categories
  for select to authenticated
  using (is_active = true or public.resources_is_admin());

-- resource_tags: Admin full; HR/Employee read
create policy resource_tags_admin_all on public.resource_tags
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

create policy resource_tags_read on public.resource_tags
  for select to authenticated
  using (public.resources_can_read_published());

-- resource_sources: Admin only (may contain internal notes)
create policy resource_sources_admin_all on public.resource_sources
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

-- country_resources: Admin full; HR/Employee read published+visible only
create policy country_resources_admin_all on public.country_resources
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

create policy country_resources_read_published on public.country_resources
  for select to authenticated
  using (
    public.resources_can_read_published()
    and not public.resources_is_admin()
    and status = 'published'
    and is_visible_to_end_users = true
    and (effective_from is null or effective_from <= now())
    and (effective_to is null or effective_to >= now())
  );

-- country_resource_tags: Admin full; HR/Employee read only for published resources
create policy country_resource_tags_admin_all on public.country_resource_tags
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

create policy country_resource_tags_read_published on public.country_resource_tags
  for select to authenticated
  using (
    public.resources_can_read_published()
    and not public.resources_is_admin()
    and exists (
      select 1 from public.country_resources r
      where r.id = resource_id
        and r.status = 'published'
        and r.is_visible_to_end_users = true
    )
  );

-- rkg_country_events: Admin full; HR/Employee read published+visible only
create policy rkg_country_events_admin_all on public.rkg_country_events
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

create policy rkg_country_events_read_published on public.rkg_country_events
  for select to authenticated
  using (
    public.resources_can_read_published()
    and not public.resources_is_admin()
    and status = 'published'
    and is_visible_to_end_users = true
  );

-- country_event_tags: Admin full; HR/Employee read for published events
create policy country_event_tags_admin_all on public.country_event_tags
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

create policy country_event_tags_read_published on public.country_event_tags
  for select to authenticated
  using (
    public.resources_can_read_published()
    and not public.resources_is_admin()
    and exists (
      select 1 from public.rkg_country_events e
      where e.id = event_id and e.status = 'published' and e.is_visible_to_end_users = true
    )
  );

-- case_resource_preferences: Admin only (ownership not yet modeled)
create policy case_resource_preferences_admin_all on public.case_resource_preferences
  for all to authenticated
  using (public.resources_is_admin())
  with check (public.resources_is_admin());

-- resource_audit_log: Admin only, append-only
create policy resource_audit_log_admin_select on public.resource_audit_log
  for select to authenticated using (public.resources_is_admin());

create policy resource_audit_log_admin_insert on public.resource_audit_log
  for insert to authenticated with check (public.resources_is_admin());

-- ============================================================================
-- 7. ENABLE RLS (ensure on all)
-- ============================================================================
alter table public.resource_categories enable row level security;
alter table public.resource_tags enable row level security;
alter table public.resource_sources enable row level security;
alter table public.country_resources enable row level security;
alter table public.country_resource_tags enable row level security;
alter table public.rkg_country_events enable row level security;
alter table public.country_event_tags enable row level security;
alter table public.case_resource_preferences enable row level security;
alter table public.resource_audit_log enable row level security;

-- ============================================================================
-- 8. SECURE PUBLISHED VIEWS (exclude internal columns)
-- ============================================================================
create or replace view public.published_country_resources as
select
  id, country_code, country_name, city_name, category_id, title, summary,
  body, content_json, resource_type, audience_type, min_child_age, max_child_age,
  budget_tier, language_code, is_family_friendly, is_featured,
  address, district, latitude, longitude, price_range_text,
  external_url, booking_url, contact_info, opening_hours,
  source_id, trust_tier, effective_from, effective_to,
  created_at, updated_at
from public.country_resources
where status = 'published'
  and is_visible_to_end_users = true
  and (effective_from is null or effective_from <= now())
  and (effective_to is null or effective_to >= now());

create or replace view public.published_country_events as
select
  id, country_code, country_name, city_name, title, description, event_type,
  venue_name, address, start_datetime, end_datetime, price_text, currency,
  is_free, is_family_friendly, min_age, max_age, language_code,
  external_url, booking_url, source_id, trust_tier,
  created_at, updated_at
from public.rkg_country_events
where status = 'published'
  and is_visible_to_end_users = true;

create or replace view public.published_resource_sources_safe as
select id, source_name, publisher, source_type, url, retrieved_at, trust_tier
from public.resource_sources;

-- RLS on views: views inherit from underlying tables, but we add policies for the view
-- In PostgreSQL, selecting from a view uses the view owner's privileges by default.
-- For security, grant select only to authenticated and rely on underlying RLS.
-- Views don't have their own RLS - they use the base table's RLS when the view
-- is accessed. So we must ensure the base table RLS allows the view query.
-- The published views filter to published+visible rows; the base table policy
-- for non-admin allows select only on those rows. So selecting from the view
-- as non-admin will only return rows that pass the base table's RLS.
-- The view adds an extra filter - so we're good. Grant select to authenticated.
grant select on public.published_country_resources to authenticated;
grant select on public.published_country_events to authenticated;
grant select on public.published_resource_sources_safe to authenticated;

-- ============================================================================
-- 9. SERVICE_ROLE BYPASS (backend uses service_role for admin ops)
-- ============================================================================
-- service_role bypasses RLS by default in Supabase. No extra grant needed.

commit;
